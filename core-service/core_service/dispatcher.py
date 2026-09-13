"""Single KARMO dispatch path for capability execution.

Every real tool invocation must resolve through the KARMO registry and approval
engine. Models never call arbitrary handlers directly and cannot lower the
required approval class. When durable persistence is configured, invocation
identity is recorded before the handler runs and approved execution may use an
atomic approval+ledger claim transaction.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .control import ApprovalRequirement, CoreControlError, arguments_digest


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
    invocation_id: str | None = None


class CapabilityDispatcher:
    def __init__(self, *, registry, approval_engine, handlers=None,
                 invocation_ledger=None, execution_coordinator=None):
        self.registry = registry
        self.approval_engine = approval_engine
        self.handlers = dict(handlers or {})
        self.invocation_ledger = invocation_ledger
        self.execution_coordinator = execution_coordinator

    def bind(self, tool_id: str, version: str, handler):
        key = (tool_id, version)
        if key in self.handlers:
            raise DispatchError(f"handler already bound: {key}")
        if not callable(handler):
            raise DispatchError("handler must be callable")
        self.handlers[key] = handler

    @staticmethod
    def _digest_result(result):
        canonical = json.dumps(result, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _begin_ledger(self, *, idempotency_key, task_id, requester, tool_id, version,
                      model_identity, executor_identity, arguments, requirement, approval_id):
        if self.invocation_ledger is None:
            return None
        if not idempotency_key:
            raise DispatchError("idempotency_key is required when durable invocation ledger is enabled")
        return self.invocation_ledger.begin(
            idempotency_key=idempotency_key,
            task_id=task_id,
            tool_id=tool_id,
            tool_version=version,
            requester=requester,
            model_identity=model_identity,
            executor_identity=executor_identity,
            arguments_digest=arguments_digest(tool_id, version, arguments),
            authority_decision=requirement.value,
            approval_id=approval_id,
        )

    def _execute_handler(self, *, invocation_id, handler, arguments):
        try:
            result = handler(arguments)
        except Exception:
            if invocation_id is not None:
                self.invocation_ledger.complete(invocation_id, status="FAILED")
            raise
        if invocation_id is not None:
            self.invocation_ledger.complete(
                invocation_id,
                status="EXECUTED",
                result_digest=self._digest_result(result),
            )
        return result

    def _require_approval_requester_binding(self, approval_id, requester):
        """Bind reusable approval identifiers to the identity that requested them.

        Tool/version/argument/executor checks prevent capability substitution, but
        without this check a caller that learns another requester's approval ID
        could reuse that authority for the same exact invocation shape. Requester
        identity is part of the durable approval record and is therefore an
        authority boundary, not merely audit metadata.
        """
        try:
            record = self.approval_engine.get(approval_id)
        except CoreControlError as exc:
            raise DispatchError(str(exc)) from exc
        if record is None:
            raise DispatchError(f"no such approval: {approval_id}")
        if record.requester != requester:
            raise DispatchError("approval requester mismatch")

    def dispatch(self, *, requester, tool_id, version, arguments, executor_identity,
                 approval_id=None, task_id=None, model_identity=None, idempotency_key=None):
        record = self.registry.get(tool_id, version)
        if record is None or record.deprecated:
            raise DispatchError(f"unregistered or deprecated capability: {(tool_id, version)}")
        key = (tool_id, version)
        handler = self.handlers.get(key)
        if handler is None:
            raise DispatchError(f"no handler bound for registered capability: {key}")

        requirement = record.computed_approval_requirement
        if requirement in (ApprovalRequirement.NONE, ApprovalRequirement.NOTIFY_ONLY):
            invocation_id = self._begin_ledger(
                idempotency_key=idempotency_key,
                task_id=task_id,
                requester=requester,
                tool_id=tool_id,
                version=version,
                model_identity=model_identity,
                executor_identity=executor_identity,
                arguments=arguments,
                requirement=requirement,
                approval_id=None,
            )
            result = self._execute_handler(
                invocation_id=invocation_id,
                handler=handler,
                arguments=arguments,
            )
            return DispatchDecision(
                tool_id=tool_id,
                version=version,
                approval_requirement=requirement,
                approval_id=None,
                executed=True,
                result=result,
                invocation_id=invocation_id,
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

        self._require_approval_requester_binding(approval_id, requester)

        if self.execution_coordinator is not None:
            if not idempotency_key:
                raise DispatchError("idempotency_key is required for durable approved execution")
            try:
                claim = self.execution_coordinator.claim(
                    approval_id=approval_id,
                    idempotency_key=idempotency_key,
                    task_id=task_id,
                    tool_id=tool_id,
                    tool_version=version,
                    requester=requester,
                    model_identity=model_identity,
                    executor_identity=executor_identity,
                    arguments=arguments,
                    authority_decision=requirement.value,
                )
            except CoreControlError as exc:
                raise DispatchError(str(exc)) from exc
            try:
                result = handler(arguments)
            except Exception:
                self.execution_coordinator.finish(claim, status="FAILED")
                if hasattr(self.approval_engine, "refresh"):
                    self.approval_engine.refresh(approval_id)
                raise
            self.execution_coordinator.finish(
                claim,
                status="EXECUTED",
                result_digest=self._digest_result(result),
            )
            if hasattr(self.approval_engine, "refresh"):
                self.approval_engine.refresh(approval_id)
            return DispatchDecision(
                tool_id=tool_id,
                version=version,
                approval_requirement=requirement,
                approval_id=approval_id,
                executed=True,
                result=result,
                invocation_id=claim.invocation_id,
            )

        invocation_id = self._begin_ledger(
            idempotency_key=idempotency_key,
            task_id=task_id,
            requester=requester,
            tool_id=tool_id,
            version=version,
            model_identity=model_identity,
            executor_identity=executor_identity,
            arguments=arguments,
            requirement=requirement,
            approval_id=approval_id,
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
            if invocation_id is not None:
                self.invocation_ledger.complete(invocation_id, status="FAILED")
            raise DispatchError(str(exc)) from exc
        except Exception:
            if invocation_id is not None:
                self.invocation_ledger.complete(invocation_id, status="FAILED")
            raise
        if invocation_id is not None:
            self.invocation_ledger.complete(
                invocation_id,
                status="EXECUTED",
                result_digest=self._digest_result(result),
            )
        return DispatchDecision(
            tool_id=tool_id,
            version=version,
            approval_requirement=requirement,
            approval_id=approval_id,
            executed=True,
            result=result,
            invocation_id=invocation_id,
        )
