"""Agent harness: memory/learning channels + model adapters.

Offline phase uses ``MockModelAdapter`` — a deterministic rule generalizer
clearly labelled in every trace (``model_name="mock-deterministic-v1"``).
Real-model adapters are OpenAI-compatible clients (GPT / GLM / Qwen all
speak that protocol); they are NEVER called unless an experiment opts in
explicitly, and every call is cost-accounted.
"""
from __future__ import annotations

CHANNELS = ("episodic", "vector_rag", "skill_consolidation",
            "policy_distillation")


class MockModelAdapter:
    """Deterministic generalizer.

    Given a retained successful CASE, it proposes the domain's ratchet
    rule: the canonical case-to-policy generalization (drop the incident
    binding, widen scope/lifetime).  Same input -> same proposal, so all
    arms A/B/C see byte-identical candidates (matched-fork requirement).
    """
    name = "mock-deterministic-v1"
    version = "1.0.0"
    is_llm = False

    def propose_rule(self, domain, memory, probe):
        if not memory:
            return None
        return dict(domain.ratchet_rule)


class LLMModelAdapter:
    """OpenAI-compatible chat adapter for the real-model phase.

    Reads keys from the environment (never logged).  Requires explicit
    ``enabled=True`` from the caller; offline code paths never construct
    it with enabled=True.
    """
    name = "unconfigured"
    version = "unset"
    is_llm = True

    def __init__(self, model_id: str, base_url_env: str = "OPENAI_BASE_URL",
                 api_key_env: str = "OPENAI_API_KEY", enabled: bool = False):
        import os
        self.model_id = model_id
        self.name = model_id
        self.base_url = os.environ.get(base_url_env, "")
        self._api_key = os.environ.get(api_key_env, "")
        self.enabled = enabled and bool(self._api_key)
        self.usage = {"calls": 0, "prompt_tokens": 0,
                      "completion_tokens": 0}

    def propose_rule(self, domain, memory, probe):
        if not self.enabled:
            raise RuntimeError(
                "LLM adapter not enabled/configured; offline phase must "
                "use MockModelAdapter")
        raise NotImplementedError(
            "wired in the pilot phase; requires user cost approval first")


class LearningAgent:
    """The (untrusted) learning agent under study.

    ``channel`` differences in the offline mock:
    - episodic:            retains every case; proposes after >=1 success
    - vector_rag:          retains top-3 most similar; proposes after >=1
    - skill_consolidation: needs >=2 successes to consolidate a pattern
    - policy_distillation: distills a rule after >=1 success
    """

    def __init__(self, model_adapter, channel: str, domain):
        if channel not in CHANNELS:
            raise ValueError(channel)
        self.model = model_adapter
        self.channel = channel
        self.domain = domain
        self.memory: list[dict] = []
        self.history_length_k = 0

    def observe(self, case_cert, request, outcome: str):
        self.memory.append({"case_id": case_cert["case_id"],
                            "request": request, "outcome": outcome,
                            "cert_kind": case_cert["kind"]})
        if outcome == "success":
            self.history_length_k += 1

    def _retained(self):
        if self.channel == "vector_rag":
            return self.memory[-3:]
        return self.memory

    def propose_rule(self, probe):
        retained = self._retained()
        successes = [m for m in retained if m["outcome"] == "success"]
        if self.channel == "skill_consolidation" and len(successes) < 2:
            return None
        if not successes:
            return None
        return self.model.propose_rule(self.domain, retained, probe)
