import asyncio
import os
import json
from my_agent.agent import create_excel_analysis_graph
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

async def main():
    checkpointer = MemorySaver()
    graph = create_excel_analysis_graph(checkpointer)
    
    input_state = {"messages": [HumanMessage(content="Plot a simple line chart for numbers 1 to 5")]}
    config = {"configurable": {"thread_id": "test_123"}, "recursion_limit": 100}
    
    with open("output_events.txt", "w", encoding="utf-8") as f:
        async for event in graph.astream(input_state, config, stream_mode="updates", subgraphs=True):
            f.write(str(event) + "\n")

if __name__ == "__main__":
    asyncio.run(main())
