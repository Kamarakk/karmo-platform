# Day 1 — LLMs + Python Control Layer

## Objective
Understand the difference between model generation and application authority by using a real local model from Python and enforcing a simple tool policy outside the model.

## Time
90 minutes.

## Outcomes
By the end of this lesson, Natalie should be able to:
- explain what the LLM does and does not control;
- make a local-model request from Python;
- receive structured output;
- validate that output;
- block a forbidden action in deterministic Python code;
- explain why model refusal alone is not a security boundary.

## Tools
- KARMO-DEV01
- Python 3.11+
- dedicated `learning-labs/.venv`
- Ollama
- one small local Qwen or Llama model
- ChatGPT for instruction/review
- Claude Code only for setup/scaffolding when needed

## Lab sequence

### Part 1 — Environment verification
Confirm Python, virtual environment, basic packages, and local Ollama availability. No production access.

### Part 2 — First real model call
Natalie writes a small Python client that sends a prompt to the local model and prints the response.

### Part 3 — Structured tool proposal
Ask the model to return a structured proposal such as:

```json
{
  "tool": "read_document",
  "arguments": {"document_id": "demo-001"}
}
```

The model is only proposing an action.

### Part 4 — Python validation
Natalie writes validation/control code that checks:
- whether the tool exists;
- whether the tool is allowed;
- whether required arguments exist;
- whether argument types are valid.

### Part 5 — Break it
Test at least these cases:
1. allowed tool;
2. forbidden tool;
3. invented tool;
4. malformed arguments;
5. malformed/non-JSON model response.

Do not immediately reveal fixes. Natalie predicts the failure, runs the case, and diagnoses it.

### Part 6 — Model comparison
If both models are already installed, send the same structured-tool task to Qwen and Llama and compare:
- schema compliance;
- invented fields;
- response consistency;
- whether either model tries to perform or narrate an unauthorized action.

If the second model is not installed yet, defer this comparison rather than installing unnecessary software during the middle of the lab.

### Part 7 — KARMO mapping
Map the lab to:
- Tool/Capability Registry: what tools exist and what authority class they have;
- Approval Engine: which actions require human approval;
- deterministic control layer: validation and enforcement outside the LLM.

## Explain-back questions
Natalie answers in her own words:
1. Why is a model-generated tool call not the same as tool execution?
2. What must Python/KARMO validate before executing a tool?
3. Why is asking the model to "never delete anything" weaker than blocking deletion in code?
4. What part of this lesson already exists conceptually in KARMO?

## Architecture challenge
If we were designing KARMO again today, should the model ever be allowed to determine its own permissions? Explain why or why not.

## Evidence
Save only learning artifacts and synthetic inputs/outputs. Do not save secrets or production data.
