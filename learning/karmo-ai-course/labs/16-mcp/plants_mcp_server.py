"""Module 16: expose a read-only KARMO capability as an MCP server.

MCP (Model Context Protocol) is the standard plug that lets any AI app
(Claude Code, Claude Desktop, IDEs, other agents) call your tools.
This server offers two read-only tools over your BloomBoss data.

Needs the course virtual environment (see Module 16 steps).
Test it:  python3 test_client.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from plant_data import cultivar_summary, list_cultivars as _list_cultivars  # noqa: E402

from mcp.server import MCPServer

mcp = MCPServer("karmo-plants")


@mcp.tool()
def list_cultivars() -> list:
    """Names of every cultivar in the BloomBoss data."""
    return _list_cultivars()


@mcp.tool()
def get_plant_stock(cultivar: str) -> dict:
    """Units, status counts, landed cost per unit and sales for one cultivar (read-only)."""
    return cultivar_summary(cultivar)


if __name__ == "__main__":
    mcp.run()  # stdio transport: the client starts this script and talks over stdin/stdout
