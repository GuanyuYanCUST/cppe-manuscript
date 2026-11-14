"""A5 (fixed decode parameters) + A6 (failure traces): extract real
examples from artifacts into docs/A5_A6_APPENDIX_DATA.md."""
import glob
import json
import pathlib

OUT = pathlib.Path("docs/A5_A6_APPENDIX_DATA.md")
md = ["# Appendix data: A5 decode parameters, A6 failure traces",
      "",
      "## A5 — Fixed decoding / sampling parameters (all five arms)",
      "",
      "One adapter configuration for every rollout; no per-run tuning:",
      "",
      "| parameter | value | note |",
      "|---|---|---|",
      "| temperature | 0.0 | except Claude-5.5: upstream rejects 0 |",
      "| | | (HTTP 400); preset forces 1.0 for that provider |",
      "| max_output_tokens | 2048 | pilot-verified; earlier 1024 for |",
      "| | | GLM thinking mode |",
      "| max_retries | 2 | exponential backoff, retryable codes only |",
      "| GLM-5.3 thinking | enabled + reasoning_effort=low | always-on |",
      "| | | thinker; disabled -> HTTP 400 |",
      "| Claude-5.5 | temperature=1.0 forced by preset | see above |",
      "| Gemini / DeepSeek / GPT | no extra payload | |",
      "| seed / top_p | not set (endpoint defaults) | deterministic |",
      "| | | decode is NOT claimed; frozen-trajectory replay is the |",
      "| | | determinism boundary (see REAL_LLM_EXPERIMENT_REPORT §8) |",
      "",
      "## A6 — Failure traces (verbatim from artifacts)",
      ""]

# 1. MALFORMED rule example (GLM invented syntax)
for p in sorted(glob.glob(
        "results/real_glm53/rollouts/main/*.json")):
    t = json.loads(open(p, encoding="utf-8").read())
    if t["final"]["rule"]:
        conds = t["final"]["rule"].get("conditions", {})
        if any(not (isinstance(c, (list, tuple)) and len(c) == 2
                    and c[0] in ("eq", "le", "ge", "any"))
               for c in conds.values()):
            md += ["### A6.1 MALFORMED_RULE (invented condition syntax)",
                   f"- trajectory `{p.split('/')[-1]}`, final rule:",
                   "```json",
                   json.dumps(t["final"]["rule"], indent=1,
                              ensure_ascii=False), "```",
                   "- replay verdict: rejected whole (fail-closed, no",
                   "  silent repair); ATC still 100% via case channel.",
                   ""]
            break

# 2. OUT_OF_ROOT attacker reject (any arm)
for p in sorted(glob.glob(
        "results/real_gemini38flash/rollouts/main/*-atk.json")):
    t = json.loads(open(p, encoding="utf-8").read())
    if t["final"]["rule"]:
        md += ["### A6.2 OUT_OF_ROOT (attacker ratchet rejected by PG)",
               f"- trajectory `{p.split('/')[-1]}`, final rule:",
               "```json",
               json.dumps(t["final"]["rule"], indent=1,
                          ensure_ascii=False), "```",
               "- PG replay: not installed, 0 unauthorized effects;",
               "  B1 replay of the same trajectory installs it with an",
               "  unauthorized standing effect.",
               ""]
        break

# 3. Claude string-typed bounds (the strict-typing artifact)
for p in sorted(glob.glob(
        "results/real_claude55/rollouts/main/*.json")):
    t = json.loads(open(p, encoding="utf-8").read())
    r = t["final"]["rule"]
    if r and any(isinstance(v, (list, tuple)) and len(v) == 2
                 and isinstance(v[1], str)
                 and v[1].lstrip("-").replace(".", "", 1).isdigit()
                 for v in r.get("conditions", {}).values()):
        md += ["### A6.3 String-typed numeric bounds (Claude-5.5)",
               f"- trajectory `{p.split('/')[-1]}`, final rule:",
               "```json",
               json.dumps(r, indent=1, ensure_ascii=False), "```",
               "- 158/166 (95%) of Claude final rules look like this;",
               "  under strict typing the bounds never match (`eq '1'`",
               "  vs int 1) -> VPA 0.000; under lossless coercion VPA",
               "  0.366 (see report §5.2).",
               ""]
        break

# 4. Claude case-only final (declined to widen)
for p in sorted(glob.glob(
        "results/real_claude55/rollouts/main/*.json")):
    t = json.loads(open(p, encoding="utf-8").read())
    if t["final"]["mode"] == "case" and not t["final"]["rule"]:
        md += ["### A6.4 Case-only final choice (Claude-5.5)",
               f"- trajectory `{p.split('/')[-1]}`: after 10 successful",
               "  CASE-mediated tasks the model still chose `case` mode",
               "  with no standing rule. 396/800 Claude trajectories",
               "  end this way (vs 0 for GLM) — the personality",
               "  spectrum of Fig 8.",
               ""]
        break

# 5. GPT <think> inline block (raw response)
for f in sorted(glob.glob("results/real_gpt56/raw/rollout-main-*.jsonl")):
    hit = False
    for line in open(f, encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        body = r.get("response_body") or ""
        if "<think>" in body:
            md += ["### A6.5 Inline `<think>` block before JSON (GPT-5.6)",
                   f"- raw log `{f.split('/')[-1]}`, first 300 chars of",
                   "  response body:",
                   "```",
                   body[:300].replace("\n", "\\n"), "```",
                   "- `_parse_obj` strips balanced think-blocks before",
                   "  JSON extraction; truncated think replies stay",
                   "  None (fail-closed).",
                   ""]
            hit = True
            break
    if hit:
        break

OUT.write_text("\n".join(md), encoding="utf-8")
print("wrote", OUT, f"({len(md)} lines)")
