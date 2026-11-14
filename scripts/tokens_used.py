"""Sum real GLM-5.3 token usage + cost from every raw cache file."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
raw = ROOT / "results" / "real_glm53" / "raw"
PIN, POUT = 1.10, 3.90          # ¥ per 1M tokens (glm-5.3)

groups = {"rollout-main": [0, 0, 0], "rollout-acceptance": [0, 0, 0],
          "resample": [0, 0, 0]}
tot = [0, 0, 0]
for p in sorted(raw.glob("*.jsonl")):
    g = next((k for k in groups if p.name.startswith(k)), None)
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            body = json.loads(line)["response_body"]
            if isinstance(body, str):
                body = json.loads(body)
            u = body["usage"]
        except (ValueError, KeyError, TypeError):
            continue
        pt, ct = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        tot[0] += pt
        tot[1] += ct
        tot[2] += 1
        if g:
            groups[g][0] += pt
            groups[g][1] += ct
            groups[g][2] += 1


def show(name, v):
    cost = (v[0] * PIN + v[1] * POUT) / 1e6
    print(f"{name:22} calls={v[2]:5}  prompt={v[0]:9,}  "
          f"completion={v[1]:8,}  ¥{cost:.2f}")


for k, v in groups.items():
    show(k, v)
show("TOTAL(real_glm53)", tot)
# pilot was a separate frozen cache
pilot = ROOT / "results" / "LLM_PILOT" / "freeze"
pf = list(pilot.rglob("*.jsonl"))
pv = [0, 0, 0]
for p in pf:
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            body = json.loads(line)["response_body"]
            if isinstance(body, str):
                body = json.loads(body)
            u = body["usage"]
        except (ValueError, KeyError, TypeError):
            continue
        pv[0] += u.get("prompt_tokens", 0)
        pv[1] += u.get("completion_tokens", 0)
        pv[2] += 1
show("PILOT(frozen)", pv)
grand = [a + b for a, b in zip(tot, pv)]
show("GRAND TOTAL", grand)
