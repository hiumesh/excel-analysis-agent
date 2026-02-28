import asyncio
from typing import Any, Dict

import pandas as pd


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
