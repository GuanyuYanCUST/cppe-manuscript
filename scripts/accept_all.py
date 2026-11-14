"""Five-arm final acceptance: grid completeness, replay health, master
numbers (k=10 + attacker S5), per-arm cost from raw jsonl."""
import glob
import json
import pathlib

ARMS = [("GLM-5.3", "real_glm53"), ("Claude-5.5", "real_claude55"),
        ("Gemini-3.8-flash", "real_gemini38flash"),
        ("DeepSeek-v4.1-flash", "real_deepseek41flash"),
        ("GPT-5.6", "real_gpt56")]
DOMAINS = ("cloudops", "procurement", "finance", "dataaccess")
CHANNELS = ("episodic", "vector_rag", "skill_consolidation",
            "policy_distillation")
PRICE = {"real_glm53": (1.10, 3.90), "real_claude55": (3.00, 3.00),
         "real_gemini38flash": (0.30, 2.50), "real_deepseek41flash":
         (0.50, 2.00), "real_gpt56": (2.50, 10.00)}

print("== grid completeness ==")
ok_all = True
for name, d in ARMS:
    have = {pathlib.Path(p).name for p in
            glob.glob(f"results/{d}/rollouts/main/*.json")}
    missing = 0
    for dom in DOMAINS:
        for ch in CHANNELS:
            for s in range(50):
                if f"{dom}-{ch}-s{s:03d}.json" not in have:
                    missing += 1
        for s in range(50):
            if f"{dom}-episodic-s{s:03d}-atk.json" not in have:
                missing += 1
    s = json.load(open(f"results/{d}/replay/main_summary.json"))
    line_ok = missing == 0 and s["replay_errors"] == 0
    ok_all &= line_ok
    print(f"{name:20s} files={len(have):4d} missing={missing:3d} "
          f"replay_rows={s['n_rows']} replay_err={s['replay_errors']} "
          f"{'OK' if line_ok else 'FAIL'}")
print("ALL OK" if ok_all else "!! GAPS PRESENT")

print("\n== master numbers k=10 legit ==")
for name, d in ARMS:
    s = json.load(open(f"results/{d}/replay/main_summary.json"))
    c = s["cells"]
    pg, b1 = c["PG|k=10"], c["B1|k=10"]
    s5 = s["acceptance"]["S5_out_of_envelope_proposal"]
    sc2 = s["acceptance"]["S2_case_only"]
    print(f"{name:20s} propose={b1['propose_rate']:.2f} "
          f"B1install={b1['install_rate']:.2f} B1_UER={b1['UER']:.3f} "
          f"PG_UER={pg['UER']:.3f} PG_VPA="
          f"{round(pg['VPA'],3) if pg['VPA'] is not None else 0} "
          f"case_only={sc2['case_mode_count']}/{sc2['n']} "
          f"task_ok={sc2['task_success_rate_legit']:.3f} "
          f"atkS5={s5['n_out_of_envelope_proposals']}"
          f"(PG rej {s5['pg_rejected_all']}, B1 unauth "
          f"{s5['b1_unauth_effect']})")

print("\n== cost from raw jsonl ==")
tot = 0.0
for name, d in ARMS:
    tin = tout = calls = 0
    for f in glob.glob(f"results/{d}/raw/rollout-main-*.jsonl"):
        for line in open(f, encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if r.get("status") != 200:
                continue
            try:
                u = json.loads(r["response_body"]).get("usage") or {}
            except Exception:  # noqa: BLE001
                u = {}
            tin += u.get("prompt_tokens", 0) or 0
            tout += u.get("completion_tokens", 0) or 0
            calls += 1
    pin, pout = PRICE[d]
    cost = (tin * pin + tout * pout) / 1e6
    tot += cost
    print(f"{name:20s} ok_calls={calls:6d} in={tin/1e6:7.2f}M "
          f"out={tout/1e6:6.2f}M est=${cost:7.2f}")
print(f"{'TOTAL':20s} est=${tot:.2f}")
