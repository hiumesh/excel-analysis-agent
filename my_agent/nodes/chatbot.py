"""Chatbot node for handling general queries without file uploads."""

from typing import Any, Dict

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from my_agent.core.infisical_client import aget_secret
from my_agent.models.state import ExcelAnalysisState


CHATBOT_SYSTEM_PROMPT = """You are a helpful AI assistant specialized in Excel data analysis.

When users interact with you:
- If they upload an Excel file, you'll analyze it and provide insights
- If they ask general questions, provide helpful information about Excel analysis, data science, or related topics
- Be friendly, concise, and helpful

You can help with:
- Explaining data analysis concepts
- Suggesting analysis approaches for Excel data
- Answering questions about pandas, matplotlib, and data visualization
- Providing general advice on working with spreadsheet data

If the user wants to analyze data, politely ask them to upload an Excel file (.xlsx, .xls, or .csv).
"""


async def chatbot_node(state: ExcelAnalysisState) -> Dict[str, Any]:
    """
    Chatbot Node - Handles general queries without file uploads.

    This node responds to user questions when:
    - No Excel file has been uploaded
    - No previous analysis context exists
    - User is asking general questions or needs guidance

    Args:
        state: Current state containing messages

    Returns:
        Dictionary with messages update
    """
    print("💬 Chatbot: Responding to general query...")

    # Initialize LLM
    llm = init_chat_model(
        model="gpt-4o",
        api_key=await aget_secret("OPENAI_API_KEY"),
        temperature=0.7,  # Slightly higher temperature for conversational responses
    )

    # Get user's query from messages
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    user_query = user_messages[-1].content if user_messages else "Hello"

    # Create conversation with context
    system_prompt = SystemMessage(content=CHATBOT_SYSTEM_PROMPT)
    user_prompt = HumanMessage(content=str(user_query))

    # Get response from LLM
    response = await llm.ainvoke([system_prompt, user_prompt])

    print(f"✅ Chatbot: Response generated ({len(response.content)} characters)")

    return {"messages": [response]}
