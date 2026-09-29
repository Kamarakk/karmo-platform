# Module 11 · Native tool calling

**Time:** 35 minutes · **Course reference:** `code/03-ai-agents/02-openai-functions/main.py` and `03-multi-tool-versatile/main.py`

**The idea:** Instead of begging for JSON, you pass a `tools` list and Ollama returns structured `tool_calls`. Cleaner and more reliable. Results go back as `role: "tool"` messages. KARMO's general chat works exactly this way.

## Steps

**1. See the tool definitions.**
```bash
grep -n "\"name\"" ~/Desktop/KARMO-AI-Course/labs/11-native-tools/tools_agent.py
```
You should see `get_plant_stock`, `list_cultivars`, and `calculate`.

**2. Ask a one-tool question.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/11-native-tools && python3 tools_agent.py "What is the landed cost per unit of Pink Black Velvet?"
```
You should see `[step 1] get_plant_stock(...) -> {...}` and an answer with `54.24`.

**3. Ask a two-tool question.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/11-native-tools && python3 tools_agent.py "What was the margin on the Pink Black Velvet I sold? Use calculate."
```
You should see `get_plant_stock` then `calculate` with `235 - 54.24`, and an answer near `180.76`.

**4. Ask it to list everything.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/11-native-tools && python3 tools_agent.py "Which cultivars do I have?"
```
You should see `list_cultivars` called and your cultivar names.

**5. Check the answer against the data yourself.**
```bash
cd ~/Desktop/KARMO-AI-Course/labs/common && python3 -c "from plant_data import cultivar_summary as s; print(s('Pink Black Velvet'))"
```
You should see `landed_cost_per_unit: 54.24`, `units_sold: 1`, `revenue: 235.0`.

**6. Compare with KARMO.**
```bash
grep -n "\"type\": \"function\"" ~/KARMO-DEV/core-service/core_service/*.py | head
```
You should see KARMO's own tool definitions in the same format.

## Done when
- [ ] You saw a two-tool chain
- [ ] You verified one number against the data by hand
