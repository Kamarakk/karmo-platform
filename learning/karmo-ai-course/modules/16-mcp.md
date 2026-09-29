# Module 16 · MCP (Model Context Protocol)

**Time:** 35 minutes · **Beyond the course**

**The idea:** MCP is the standard plug for AI tools. Write a tool server once and any MCP client (Claude Code, Claude Desktop, other agents) can use it. You'll expose your BloomBoss data as an MCP server and plug it into Claude Code.

**Needs:** the `.venv` from Module 15, step 1.

## Steps

**1. Read the server. It's short.**
```bash
cat ~/Desktop/KARMO-AI-Course/labs/16-mcp/plants_mcp_server.py
```
You should see `MCPServer("karmo-plants")` and two `@mcp.tool()` functions: `list_cultivars` and `get_plant_stock`.

**2. Test it with a client, the way Claude Code would call it.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/16-mcp && ~/Desktop/KARMO-AI-Course/.venv/bin/python test_client.py
```
You should see `Tools offered: ['list_cultivars', 'get_plant_stock']` and `get_plant_stock -> {... "landed_cost_per_unit": 54.24, "units_sold": 1, "revenue": 235.0 ...}`.

**3. Plug it into Claude Code.**
```bash
claude mcp add karmo-plants -- ~/Desktop/KARMO-AI-Course/.venv/bin/python ~/Desktop/KARMO-AI-Course/labs/16-mcp/plants_mcp_server.py
```
You should see `Added stdio MCP server karmo-plants`.

**4. Confirm it's connected.**
```bash
claude mcp list
```
You should see `karmo-plants: ... ✓ Connected`.

**5. Use it from Claude Code.**
```bash
cd ~/Desktop && claude
```
Type: `Using karmo-plants, which cultivar has the highest landed cost per unit?` Approve the tool call when asked. You should see Claude call `list_cultivars` and `get_plant_stock` and answer from your data. Type `/exit` when done.

**6. Remove it when you're done experimenting (optional).**
```bash
claude mcp remove karmo-plants
```
You should see `Removed MCP server karmo-plants`.

## Done when
- [ ] `test_client.py` printed your Pink Black Velvet numbers
- [ ] Claude Code answered a question through your server

**KARMO link:** one MCP server can expose KARMO's BloomBoss tools to every client, instead of rewriting them per app. Adding it to KARMO itself is a Tier 3 decision.
