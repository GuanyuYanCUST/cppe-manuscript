"""CloudOps-style local tool sandbox (no production systems, ever).

Complete mediation: the sandbox is the ONLY component that can mutate the
simulated resource state, and it only executes a request carrying a PEP
admission.  "Tool effect" therefore means an actual state mutation we can
assert on, not model text.
"""
from __future__ import annotations

import itertools


class ToolSandbox:
    def __init__(self, domain):
        self.domain = domain
        self.state = {"iam_bindings": {}, "approvals": [], "transfers": [],
                      "file_reads": [], "operations": 0}
        self.effect_log: list[dict] = []
        self._ids = itertools.count(1)

    def execute(self, principal: str, request: dict, admitted: bool,
                admission_reason: str) -> dict:
        """Run a tool call.  Protected actions require admission."""
        effect = {
            "effect_id": f"FX{next(self._ids):05d}",
            "principal": principal,
            "request": request,
            "admitted": admitted,
            "admission_reason": admission_reason,
            "state_changed": False,
        }
        if not admitted:
            self.effect_log.append(effect)
            return effect
        if self.domain.is_standing(request):
            self.state["operations"] += 1
            effect["state_changed"] = True
        elif request["action"] == "attach_role":
            bindings = self.state["iam_bindings"].setdefault(
                request["resource"], [])
            bindings.append(request["attrs"])
            effect["state_changed"] = True
        elif request["action"] == "modify_iam_binding":
            self.state["iam_bindings"].setdefault(
                request["resource"], []).append(request["attrs"])
            effect["state_changed"] = True
        elif request["action"] == "approve_purchase_order":
            self.state["approvals"].append(request)
            effect["state_changed"] = True
        elif request["action"] == "wire_transfer":
            self.state["transfers"].append(request)
            effect["state_changed"] = True
        elif request["action"] == "read_restricted_file":
            self.state["file_reads"].append(request)
            effect["state_changed"] = True
        else:
            self.state["operations"] += 1
            effect["state_changed"] = True
        self.effect_log.append(effect)
        return effect

    def protected_effects(self) -> list[dict]:
        return [e for e in self.effect_log
                if e["request"]["action"] in self.domain.protected_actions
                and e["state_changed"]]
