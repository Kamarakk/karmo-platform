"""Day 1, Part 4: deterministic validation/control code.

YOU write the logic in this file. This is a starter only -- the TODOs
below are reminders of what each part needs, not a solution.

This is the actual security boundary for the lesson: the model can
PROPOSE any tool call it wants, but nothing runs unless this code (not
the model) says it's allowed. This maps to KARMO's Tool/Capability
Registry and Approval Engine -- see Part 7 of the lesson.
"""

# TODO: define the small set of tools this lab allows, and what
# arguments each one requires. Example shape (fill in for real):
#
# ALLOWED_TOOLS = {
#     "read_document": {"document_id": str},
# }
ALLOWED_TOOLS = {}


def validate_tool_call(raw_response: str) -> dict:
    """Part 4: validate a model's raw (untrusted) text response as a tool
    call.

    TODO -- check, in order, and raise/return a clear reason for whichever
    check fails first:
    1. Is `raw_response` valid JSON at all? (Part 5, case 5: malformed/
       non-JSON response)
    2. Does the parsed object have a "tool" field naming a tool that
       exists in ALLOWED_TOOLS? (Part 5, cases 2-3: forbidden/invented tool)
    3. Are all required arguments present with the right types? (Part 5,
       case 4: malformed arguments)
    4. If everything passes, return the validated tool call -- but do NOT
       execute anything here. This function only validates.

    Think about what you return/raise on each failure so the caller can
    explain *why* something was refused, not just that it was refused.
    """
    raise NotImplementedError("Part 4: write your validation logic here")


if __name__ == "__main__":
    # TODO: work through Part 5's 5 cases here, one at a time:
    #   1. allowed tool
    #   2. forbidden tool
    #   3. invented tool
    #   4. malformed arguments
    #   5. malformed/non-JSON model response
    #
    # Predict what should happen BEFORE you run each case.
    pass
