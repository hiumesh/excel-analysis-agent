import asyncio
import os
from typing import Any, Dict, Tuple

import pandas as pd

from my_agent.core.config import AgentConfig


async def convert_xlsx_to_csv(file_path: str) -> str:
    """Convert an .xlsx file to .csv for faster subsequent reads.

    Writes the CSV alongside the original file (same directory, .csv extension).
    Returns the path to the CSV file. If the CSV already exists and is newer
    than the source, it is reused without re-converting.
    """
    csv_path = os.path.splitext(file_path)[0] + ".csv"

    # Skip conversion if the CSV already exists and is up-to-date
    if os.path.exists(csv_path):
        xlsx_mtime = os.path.getmtime(file_path)
        csv_mtime = os.path.getmtime(csv_path)
        if csv_mtime >= xlsx_mtime:
            return csv_path

    def _convert():
        df = pd.read_excel(file_path)
        df.to_csv(csv_path, index=False)
        return csv_path

    return await asyncio.to_thread(_convert)


async def load_excel_file_sampled(
    file_path: str,
    sample_rows: int = AgentConfig.DATA_INSPECTOR_SAMPLE_ROWS,
) -> Tuple[pd.DataFrame, int]:
    """Load a sample of the file for quick data inspection.

    For large .xlsx files, converts to CSV first for speed.
    Returns (sampled_df, total_row_count).
    """
    # Check file size
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    is_large = file_size_mb >= AgentConfig.LARGE_FILE_THRESHOLD_MB

    # Convert large .xlsx → .csv for faster I/O
    effective_path = file_path
    if is_large and file_path.lower().endswith((".xlsx", ".xls")):
        effective_path = await convert_xlsx_to_csv(file_path)

    if effective_path.lower().endswith(".csv"):
        # Count total rows efficiently (only scan newlines)
        def _count_rows():
            with open(effective_path, "r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f) - 1  # subtract header

        total = await asyncio.to_thread(_count_rows)

        # Read only the sample
        try:
            df = await asyncio.to_thread(pd.read_csv, effective_path, nrows=sample_rows)
        except UnicodeDecodeError:
            df = await asyncio.to_thread(
                pd.read_csv, effective_path, nrows=sample_rows, encoding="unicode_escape"
            )
    else:
        # Small .xlsx — read fully (openpyxl has no native nrows)
        df_full = await asyncio.to_thread(pd.read_excel, file_path)
        total = len(df_full)
        df = df_full.head(sample_rows)

    return df, total


async def load_excel_file(file_path: str) -> pd.DataFrame:
    """
    Load an Excel or CSV file into a pandas DataFrame.

    Args:
        file_path: Path to the Excel or CSV file

    Returns:
        pandas DataFrame containing the data
    """
    try:
        if file_path.lower().endswith(".csv"):
            try:
                df = await asyncio.to_thread(pd.read_csv, file_path)
            except UnicodeDecodeError:
                df = await asyncio.to_thread(
                    pd.read_csv, file_path, encoding="unicode_escape"
                )
        else:
            # Wrap the blocking pd.read_excel in asyncio.to_thread
            df = await asyncio.to_thread(pd.read_excel, file_path)
        return df
    except Exception as e:
        raise ValueError(f"Error loading file: {str(e)}")


async def analyze_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze a DataFrame and extract key information.

    Args:
        df: pandas DataFrame to analyze

    Returns:
        Dictionary containing analysis results
    """

    # Wrap the blocking pandas operations in asyncio.to_thread
    def _analyze():
        numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()
        categorical_columns = df.select_dtypes(
            include=["object", "category"]
        ).columns.tolist()

        analysis = {
            "num_rows": len(df),
            "num_columns": len(df.columns),
            "column_names": df.columns.tolist(),
            "column_types": {str(k): str(v) for k, v in df.dtypes.to_dict().items()},
            "missing_values": df.isnull().sum().to_dict(),
            "numeric_columns": numeric_columns,
            "categorical_columns": categorical_columns,
            "sample_rows": df.head(5).to_dict("records"),
            "unique_counts": {col: df[col].nunique() for col in df.columns},
        }

        # Numeric statistics
        if numeric_columns:
            analysis["numeric_stats"] = df[numeric_columns].describe().to_dict()

            # Zero ratios
            analysis["zero_ratios"] = {
                col: float((df[col] == 0).mean()) for col in numeric_columns
            }

        # Categorical sample values
        analysis["categorical_samples"] = {
            col: df[col].astype(str).unique()[:20].tolist()
            for col in categorical_columns
        }

        return analysis

    return await asyncio.to_thread(_analyze)


async def generate_data_description(analysis: Dict[str, Any]) -> str:
    """
    Generate a human-readable description of the Excel data.

    Args:
        analysis: Dictionary containing analysis results

    Returns:
        Textual description of the data
    """
    # This is pure string manipulation, no blocking I/O, so it's fine as-is
    description_parts = [
        "Dataset Overview:",
        f"- Total rows: {analysis['num_rows']}",
        f"- Total columns: {analysis['num_columns']}",
        "\nColumn Information:",
        f"- Numeric columns ({len(analysis['numeric_columns'])}): {', '.join(analysis['numeric_columns'])}",
        f"- Categorical columns ({len(analysis['categorical_columns'])}): {', '.join(analysis['categorical_columns'])}",
    ]

    # Add missing value information
    missing = {k: v for k, v in analysis["missing_values"].items() if v > 0}
    if missing:
        description_parts.append("\nMissing Values:")
        for col, count in missing.items():
            description_parts.append(f"- {col}: {count} missing values")
    else:
        description_parts.append("\nNo missing values detected.")

    # Add sample data
    description_parts.append("\nSample Data (first 5 rows):")
    for i, row in enumerate(analysis["sample_rows"], 1):
        description_parts.append(f"Row {i}: {row}")

    # Add numeric statistics if available
    if "numeric_stats" in analysis:
        description_parts.append("\nNumeric Column Statistics:")
        for col in analysis["numeric_columns"]:
            stats = analysis["numeric_stats"][col]
            description_parts.append(
                f"- {col}: mean={stats['mean']:.2f}, std={stats['std']:.2f}, "
                f"min={stats['min']:.2f}, max={stats['max']:.2f}"
            )

    return "\n".join(description_parts)
