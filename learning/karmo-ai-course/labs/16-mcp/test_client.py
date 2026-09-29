"""Calls the MCP server the same way Claude Code would. Run: python3 test_client.py"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = Path(__file__).resolve().parent / "plants_mcp_server.py"


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Tools offered:", [t.name for t in tools.tools])
            result = await session.call_tool("get_plant_stock", {"cultivar": "Pink Black Velvet"})
            print("get_plant_stock ->", result.content[0].text)


asyncio.run(main())
