"""Single KARMO dispatch path for capability execution.

Every real tool invocation must resolve through the KARMO registry and approval
engine. Models never call arbitrary handlers directly and cannot lower the
required approval class.
"""

from __future__ import annotations

from dataclasses import dataclass

from .control import ApprovalRequirement, CoreControlError


class DispatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class DispatchDecision:
    tool_id: str
    version: str
    approval_requirement: ApprovalRequirement
    approval_id: str | None
    executed: bool
    result: object | None = None


class CapabilityDispatcher:
    def __init__(self, *, registry, approval_engine, handlers=None):
        self.registry = registry
        self.approval_engine = approval_engine
        self.handlers = dict(handlers or {})

    def bind(self, tool_id: str, version: str, handler):
        key = (tool_id, version)
        if key in self.handlers:
            raise DispatchError(f"handler already bound: {key}")
        if not callable(handler):
            raise DispatchError("handler must be callable")
        self.handlers[key] = handler

    def dispatch(self, *, requester, tool_id, version, arguments, executor_identity, approval_id=None):
        record = self.registry.get(tool_id, version)
        if record is None or record.deprecated:
            raise DispatchError(f"unregistered or deprecated capability: {(tool_id, version)}")
        key = (tool_id, version)
        handler = self.handlers.get(key)
        if handler is None:
            raise DispatchError(f"no handler bound for registered capability: {key}")

        requirement = record.computed_approval_requirement
        if requirement in (ApprovalRequirement.NONE, ApprovalRequirement.NOTIFY_ONLY):
            return DispatchDecision(
                tool_id=tool_id,
                version=version,
                approval_requirement=requirement,
                approval_id=None,
                executed=True,
                result=handler(arguments),
            )

        if approval_id is None:
            pending = self.approval_engine.request(
                requester=requester,
                tool_id=tool_id,
                tool_version=version,
                arguments=arguments,
                authority_class=requirement.value,
            )
            return DispatchDecision(
                tool_id=tool_id,
                version=version,
                approval_requirement=requirement,
                approval_id=pending.approval_id,
                executed=False,
            )

        try:
            result = self.approval_engine.execute(
                approval_id,
                tool_id=tool_id,
                tool_version=version,
                arguments=arguments,
                executor_identity=executor_identity,
                action=lambda: handler(arguments),
            )
        except CoreControlError as exc:
            raise DispatchError(str(exc)) from exc
        return DispatchDecision(
            tool_id=tool_id,
            version=version,
            approval_requirement=requirement,
            approval_id=approval_id,
            executed=True,
            result=result,
        )
