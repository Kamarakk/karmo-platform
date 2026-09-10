"""Day 1, Parts 2-3: first real model call + structured tool proposal.

YOU write the logic in this file. This is a starter only -- the TODOs
below are reminders of what each part needs, not a solution.

Local Ollama only: http://127.0.0.1:11434
No production access. No karmo-ai01.
"""

OLLAMA_URL = "http://127.0.0.1:11434"
MODEL = "qwen2.5:1.5b"  # or "llama3.2:3b" -- try both for Part 6


def ask_model(prompt: str) -> str:
    """Part 2: send `prompt` to the local model and return its raw text
    response.

    TODO:
    - Use httpx (already installed) to POST to {OLLAMA_URL}/api/generate
      with a JSON body containing at least "model", "prompt", and
      "stream": False.
    - Parse the response and return the generated text.
    - Think about what should happen if the request fails or times out.
    """
    raise NotImplementedError("Part 2: write your model call here")


def ask_model_for_tool_proposal(user_request: str) -> str:
    """Part 3: ask the model to propose a tool call as JSON, e.g.

        {"tool": "read_document", "arguments": {"document_id": "demo-001"}}

    TODO:
    - Build a prompt that instructs the model to respond with ONLY a JSON
      object in that shape.
    - Call ask_model() (or similar) and return the raw text response.
    - Remember: this is a PROPOSAL from the model. Nothing has executed
      yet -- that's the whole point of the lesson.
    """
    raise NotImplementedError("Part 3: write your tool-proposal prompt here")


if __name__ == "__main__":
    # TODO: call ask_model() with a harmless test prompt and print the result.
    # Then call ask_model_for_tool_proposal() with a sample request and
    # print the raw (unvalidated) response -- validation happens in
    # tool_validator.py, not here.
    pass
