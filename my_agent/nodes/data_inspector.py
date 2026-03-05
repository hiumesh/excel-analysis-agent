"""Data Inspector node — analyses an Excel/CSV file and builds a rich data context."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from langchain_core.messages import AIMessage

from my_agent.helpers.sandbox_client import check_server_health, preload_file_via_server
from my_agent.core.execution_var import get_current_session_id
from my_agent.helpers.utils import (
    analyze_dataframe,
    generate_data_description,
    load_excel_file_sampled,
)
from my_agent.models.state import ExcelAnalysisState
from my_agent.tools.tools import reset_execution_context

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _error_result(
    error_msg: str,
    file_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a standardised error state-update dict."""
    return {
        "data_context": {
            "error": error_msg,
            "file_path": file_path,
            "description": None,
            "summary": {},
        },
        "messages": [AIMessage(content=error_msg, name="DataInspector")],
    }


# ---------------------------------------------------------------------------
# Sandbox health gate
# ---------------------------------------------------------------------------

async def _ensure_sandbox_healthy() -> Optional[Dict[str, Any]]:
    """Return an error state-update if the sandbox is unreachable, else ``None``."""
    try:
        healthy = await check_server_health()
        if not healthy:
            msg = (
                "Sandbox server is not running or unhealthy. "
                "Please start the server in a separate terminal:\n"
                "  python run_sandbox_server.py"
            )
            logger.error(msg)
            return _error_result(msg)
    except Exception as exc:
        msg = (
            f"Cannot connect to sandbox server: {exc}\n"
            "Please start the server in a separate terminal:\n"
            "  python run_sandbox_server.py"
        )
        logger.error(msg)
        return _error_result(msg)

    return None  # healthy


# ---------------------------------------------------------------------------
# Semantic profiling helpers
# ---------------------------------------------------------------------------

def _detect_semantic_roles(column_names: List[str], numeric_cols: List[str]) -> Dict[str, str]:
    """Classify each column into a semantic role (metric, time_dimension, etc.)."""
    roles: Dict[str, str] = {}
    for col in column_names:
        col_lower = col.lower()
        if col in numeric_cols:
            roles[col] = "metric"
        elif "month" in col_lower or "date" in col_lower:
            roles[col] = "time_dimension"
        elif "proj" in col_lower or "budget" in col_lower or "type" in col_lower:
            roles[col] = "scenario_dimension"
        elif "fund" in col_lower or "code" in col_lower:
            roles[col] = "identifier_dimension"
        else:
            roles[col] = "category_dimension"
    return roles


def _detect_scenarios(categorical_samples: Dict[str, List[str]]) -> tuple[bool, List[str]]:
    """Detect projection/budget scenario values in categorical columns."""
    scenario_values: List[str] = []
    for _col, samples in categorical_samples.items():
        lower_samples = [str(v).lower() for v in samples]
        if any("proj" in val or "budget" in val for val in lower_samples):
            scenario_values.extend(lower_samples)

    unique = list(set(scenario_values))[:10]
    return len(scenario_values) > 0, unique


def _detect_structure_type(
    df: pd.DataFrame,
    has_scenarios: bool,
    scenario_values: List[str],
) -> str:
    """Determine whether the dataset looks like a snapshot-based forecast."""
    if "Month" in df.columns and has_scenarios:
        month_vals = df["Month"].astype(str).str.lower().unique()
        if any(val in scenario_values for val in month_vals):
            return "snapshot_based_forecast"
    return "standard_tabular"


def _compute_entity_distribution(df: pd.DataFrame) -> Dict[str, int]:
    """Heuristic keyword counts for revenue / expense / capex rows."""
    revenue_kw = ["fees", "income", "grant", "tuition"]
    expense_kw = ["travel", "equipment", "maintenance", "upgrade"]
    capex_kw = ["-5y", "-3y", "implementation", "intangibles"]

    if "Description" not in df.columns:
        return {"revenue": 0, "expense": 0, "capex": 0}

    descriptions = df["Description"].astype(str).str.lower()
    return {
        "revenue": int(descriptions.str.contains("|".join(revenue_kw)).sum()),
        "expense": int(descriptions.str.contains("|".join(expense_kw)).sum()),
        "capex": int(descriptions.str.contains("|".join(capex_kw)).sum()),
    }


def _compute_data_quality(df: pd.DataFrame, numeric_cols: List[str]) -> Dict[str, float]:
    """Basic data-quality metrics: zero ratio, missing ratio, duplicate ratio."""
    quality: Dict[str, float] = {}

    if numeric_cols:
        first_metric = numeric_cols[0]
        quality["zero_ratio"] = float((df[first_metric] == 0).mean())
        quality["missing_ratio"] = float(df[first_metric].isna().mean())

    quality["duplicate_ratio"] = float(df.duplicated().mean())
    return quality


def _detect_granularity(unique_counts: Dict[str, int]) -> str:
    """Infer temporal granularity from the 'Month' column if present."""
    if "Month" not in unique_counts:
        return "unknown"
    return "monthly_aggregated" if unique_counts["Month"] <= 12 else "transactional_or_multi_year"


def _build_semantic_profile(
    df: pd.DataFrame,
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """Run the full semantic profiling pipeline and return the profile dict."""
    column_names: List[str] = analysis["column_names"]
    numeric_cols: List[str] = analysis["numeric_columns"]
    categorical_cols: List[str] = analysis["categorical_columns"]

    semantic_roles = _detect_semantic_roles(column_names, numeric_cols)
    has_scenarios, scenario_values = _detect_scenarios(analysis["categorical_samples"])
    structure_type = _detect_structure_type(df, has_scenarios, scenario_values)

    return {
        "metrics": numeric_cols,
        "dimensions": categorical_cols,
        "semantic_roles": semantic_roles,
        "has_scenarios": has_scenarios,
        "scenario_values_sample": scenario_values,
        "structure_type": structure_type,
        "entity_distribution": _compute_entity_distribution(df),
        "data_quality": _compute_data_quality(df, numeric_cols),
        "granularity": _detect_granularity(analysis.get("unique_counts", {})),
    }


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

async def data_inspector_node(state: ExcelAnalysisState) -> Dict[str, Any]:
    """Data Inspector Node — analyses an Excel file and generates a rich data context.

    Steps:
        1. Verify the sandbox server is reachable.
        2. Reset the Python REPL execution context.
        3. Load & analyse the Excel/CSV file.
        4. Run advanced semantic profiling.
        5. Return the enriched ``data_context`` and a summary message.

    On **any** error the node returns a user-friendly error message so the
    graph can gracefully fall back to the chat node.
    """
    logger.info("📊 Data Inspector: Starting file analysis...")

    try:
        # 1. Sandbox health gate -----------------------------------------------
        sandbox_err = await _ensure_sandbox_healthy()
        if sandbox_err is not None:
            return sandbox_err

        # 2. Reset execution context -------------------------------------------
        await reset_execution_context()

        # 3. Validate file path ------------------------------------------------
        excel_path: Optional[str] = state.get("excel_file_path")

        if not excel_path:
            logger.error("No excel_file_path found in state")
            return _error_result(
                "No Excel file was provided. Please upload an Excel file to proceed with the analysis."
            )

        logger.info("📎 Analysing file: %s", excel_path)

        # 4. Load SAMPLED data, analyse, describe --------------------------------
        df, total_rows = await load_excel_file_sampled(excel_path)
        analysis = await analyze_dataframe(df)
        data_description = await generate_data_description(analysis)
        file_name = Path(excel_path).name

        # 5. Semantic profiling ------------------------------------------------
        profile = _build_semantic_profile(df, analysis)

        # 6. Fire background preload so sandbox has full data ready ------------
        session_id = get_current_session_id()
        try:
            await preload_file_via_server(excel_path, session_id=session_id)
        except Exception:
            logger.warning("Preload request failed — coding agent will load file normally")

        # 7. Assemble data context ---------------------------------------------
        data_context: Dict[str, Any] = {
            "file_path": os.path.abspath(excel_path),
            "file_name": file_name,
            "analyzed_at": datetime.now().isoformat(),
            "description": data_description,
            "total_rows": total_rows,
            "sampled_rows": len(df),
            "summary": {
                "num_rows": total_rows,
                "num_columns": analysis["num_columns"],
                "column_names": analysis["column_names"],
                "numeric_columns": analysis["numeric_columns"],
                "categorical_columns": analysis["categorical_columns"],
            },
            "dataset_profile": profile,
        }

        inspector_message = AIMessage(
            content=(
                f"Data inspection complete.\n"
                f"Total Rows: {total_rows} (sampled {len(df)} for profiling), "
                f"Columns: {analysis['num_columns']}.\n"
                f"Structure Type: {profile['structure_type']}.\n"
                f"Scenarios Detected: {profile['has_scenarios']}."
            ),
            name="DataInspector",
        )

        logger.info(
            "=========== Data Inspector Result ===========\n"
            "  File: %s\n"
            "  Total Rows: %s (sampled: %s), Columns: %s\n"
            "  Numeric Columns: %s\n"
            "  Categorical Columns: %s\n"
            "  Structure Type: %s\n"
            "  Scenarios Detected: %s\n"
            "  Granularity: %s\n"
            "  Data Quality: %s\n"
            "=============================================",
            file_name,
            total_rows,
            len(df),
            analysis["num_columns"],
            analysis["numeric_columns"],
            analysis["categorical_columns"],
            profile["structure_type"],
            profile["has_scenarios"],
            profile["granularity"],
            profile["data_quality"],
        )

        return {"data_context": data_context, "messages": [inspector_message]}

    except Exception as exc:
        # Catch-all — ensures the graph never crashes at this node
        logger.error("Data Inspector failed: %s", exc, exc_info=True)
        return _error_result(
            f"I encountered an error while analysing the file: {exc}",
            file_path=state.get("excel_file_path"),
        )
