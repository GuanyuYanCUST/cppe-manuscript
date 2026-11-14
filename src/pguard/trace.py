"""Unified trace logger — the single JSONL schema every experiment shares
(实验计划 §15).  Written BEFORE any main experiment runs; all figures and
tables regenerate from these files only.
"""
from __future__ import annotations

import json
import os
import time

SCHEMA_VERSION = "1.0.0"

# Every field 实验计划 §15 requires, always present (null when not
# applicable) so downstream aggregation never misses a denominator.
COMMON_FIELDS = (
    "trace_id", "event_seq", "ts", "experiment", "arm", "phase",
    "seed", "domain", "model_name", "model_version", "learning_channel",
    "policy_hash", "root_epoch", "policy_version",
    "case_id", "case_issuer", "case_scope", "case_expiry", "case_success",
    "history_length_k",
    "candidate_rule_raw", "candidate_rule_ast", "candidate_rule_hash",
    "precedent_cap_present", "precedent_issuer", "issuer_authorized",
    "containment_oracle", "necessity_oracle",
    "guard_decision", "reject_reason",
    "policy_store_commit", "installed_rule_id", "install_path",
    "later_request", "pep_decision", "pep_reason", "tool_effect",
    "latency_auth_ms", "latency_verify_ms", "latency_total_ms",
    "crypto_backend", "notes",
)


class TraceLogger:
    def __init__(self, out_path: str, run_id: str, *, experiment: str,
                 seed: int, domain: str, model_name: str,
                 model_version: str, learning_channel: str,
                 phase: str = "offline-integration", crypto_backend: str = "",
                 extra_common: dict | None = None):
        self.out_path = out_path
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        self.f = open(out_path, "a", encoding="utf-8")
        self.run_id = run_id
        self.experiment = experiment
        self.seed = seed
        self.domain = domain
        self.model_name = model_name
        self.model_version = model_version
        self.learning_channel = learning_channel
        self.phase = phase
        self.crypto_backend = crypto_backend
        self.extra_common = extra_common or {}
        self._seq = 0

    def trace_id(self) -> str:
        return f"{self.run_id}-s{self.seed:04d}-e{self._seq:04d}"

    def emit(self, event: str, arm: str = "", **fields) -> dict:
        self._seq += 1
        rec = {"schema_version": SCHEMA_VERSION, "event": event,
               "run_id": self.run_id}
        rec.update(self.extra_common)
        for f in COMMON_FIELDS:
            rec[f] = fields.pop(f, None)
        rec.update(fields)          # event-specific extras
        # always-resolved identity fields (never null, never caller-set)
        rec["trace_id"] = f"{self.run_id}-s{rec.get('seed', 0):04d}-e{self._seq:04d}"
        rec["event_seq"] = self._seq
        rec["ts"] = time.time()
        # constructor-level defaults fill only unset (null) common fields,
        # so a caller can always override e.g. seed per event
        for k, v in (("experiment", self.experiment), ("arm", arm or ""),
                     ("seed", self.seed), ("domain", self.domain),
                     ("model_name", self.model_name),
                     ("model_version", self.model_version),
                     ("learning_channel", self.learning_channel),
                     ("phase", self.phase),
                     ("crypto_backend", self.crypto_backend)):
            if rec.get(k) is None:
                rec[k] = v
        self.f.write(json.dumps(rec, sort_keys=True,
                                ensure_ascii=False) + "\n")
        self.f.flush()
        return rec

    def close(self):
        self.f.close()
