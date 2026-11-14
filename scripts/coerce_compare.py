"""Strict vs coerced-typing sensitivity comparison, per arm.
Reads replay/main_summary.json vs main_coerced_summary.json."""
import json

ARMS = [("GLM-5.3", "real_glm53"), ("Claude-5.5", "real_claude55"),
        ("Gemini-3.8-flash", "real_gemini38flash"),
        ("DeepSeek-v4.1-flash", "real_deepseek41flash"),
        ("GPT-5.6", "real_gpt56")]
rows = []
for name, d in ARMS:
    a = json.load(open(f"results/{d}/replay/main_summary.json"))["cells"]
    b = json.load(open(
        f"results/{d}/replay/main_coerced_summary.json"))["cells"]
    for m in ("B1", "B3", "B6", "PG"):
        x, y = a[f"{m}|k=10"], b[f"{m}|k=10"]
        rows.append((name, m, x, y))
print(f"{'model':20s} {'m':3s} | {'UER strict':>10s} {'UER coerc':>9s}"
      f" | {'VPA strict':>10s} {'VPA coerc':>9s}"
      f" | {'install s/c':>12s} | {'malform s/c':>12s}")
for name, m, x, y in rows:
    vs = f"{x['VPA']:.3f}" if x["VPA"] is not None else "None"
    vc = f"{y['VPA']:.3f}" if y["VPA"] is not None else "None"
    print(f"{name:20s} {m:3s} | {x['UER']:10.3f} {y['UER']:9.3f}"
          f" | {vs:>10s} {vc:>9s} | {x['install_rate']:5.3f}/"
          f"{y['install_rate']:.3f} | {x['malformed']:5.3f}/"
          f"{y['malformed']:.3f}")
out = [{"model": n, "method": m, "strict": x, "coerced": y}
       for n, m, x, y in rows]
json.dump(out, open("results/TABLES/coerce_compare.json", "w"),
          indent=1, ensure_ascii=False)
print("wrote results/TABLES/coerce_compare.json")
