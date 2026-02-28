"""Utility functions for handling file uploads in LangGraph."""

import os
from typing import Optional, Sequence, Tuple

from langchain_core.messages import BaseMessage, HumanMessage


def extract_uploaded_file(messages: Sequence[BaseMessage]) -> Optional[Tuple[str, str]]:
    """
    Extract uploaded Excel file from LangGraph message attachments.

    LangGraph Studio and Cloud support file uploads via message attachments.
    This function extracts the file path and content type from the most recent
    file upload in the conversation.

    Args:
        messages: List of messages from the conversation

    Returns:
        Tuple of (file_path, content_type) if file found, None otherwise
        Supported file types: .xlsx, .xls, .csv
    """
    # Iterate through messages in reverse to find the most recent file upload
    for message in reversed(messages):
        if not isinstance(message, HumanMessage):
            continue

        # Check for file in various LangGraph attachment formats
        # Format 1: additional_kwargs with attachments
        if hasattr(message, 'additional_kwargs'):
            attachments = message.additional_kwargs.get('attachments', [])
            for attachment in attachments:
                file_path = attachment.get('path') or attachment.get('url')
                content_type = attachment.get('content_type', '').lower()

                # Check if it's an Excel/CSV file
                if file_path and _is_supported_file(file_path, content_type):
                    print(f"📎 Found uploaded file: {file_path}")
                    return (file_path, content_type)

        # Format 2: Direct file attribute (some LangGraph versions)
        if hasattr(message, 'file'):
            file_info = message.file
            if isinstance(file_info, dict):
                file_path = file_info.get('path') or file_info.get('url')
                content_type = file_info.get('type', '').lower()

                if file_path and _is_supported_file(file_path, content_type):
                    print(f"📎 Found uploaded file: {file_path}")
                    return (file_path, content_type)

        # Format 3: Files array (newer LangGraph versions)
        if hasattr(message, 'files'):
            for file_info in message.files:
                file_path = file_info.get('path') or file_info.get('url')
                content_type = file_info.get('content_type', '').lower()

                if file_path and _is_supported_file(file_path, content_type):
                    print(f"📎 Found uploaded file: {file_path}")
                    return (file_path, content_type)

    return None


def _is_supported_file(file_path: str, content_type: str) -> bool:
    """
    Check if the file is a supported Excel/CSV format.

    Args:
        file_path: Path or URL to the file
        content_type: MIME type of the file

    Returns:
        True if file is supported, False otherwise
    """
    # Check by file extension
    file_ext = os.path.splitext(file_path)[1].lower()
    supported_extensions = {'.xlsx', '.xls', '.csv'}

    if file_ext in supported_extensions:
        return True

    # Check by content type
    supported_types = {
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
        'application/vnd.ms-excel',  # .xls
        'text/csv',  # .csv
        'application/csv',  # .csv alternative
    }

    if content_type in supported_types:
        return True

    return False


def has_uploaded_file(messages: Sequence[BaseMessage]) -> bool:
    """
    Check if any message in the conversation has an uploaded file.

    Args:
        messages: List of messages from the conversation

    Returns:
        True if a supported file upload is found, False otherwise
    """
    return extract_uploaded_file(messages) is not None
