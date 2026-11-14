"""One-shot probe of every JSON the eval-section renderer reads, so the
renderer never guesses a key."""
import json
import pathlib

R = pathlib.Path("results/TABLES")


def peek(name, obj, depth=0, maxdepth=3):
    pad = "  " * depth
    if isinstance(obj, dict):
        ks = list(obj)[:6]
        print(f"{pad}{name}: dict[{len(obj)}] keys={ks}")
        if depth < maxdepth:
            for k in ks[:3]:
                peek(f"[{k!r}]", obj[k], depth + 1, maxdepth)
    elif isinstance(obj, list):
        print(f"{pad}{name}: list[{len(obj)}] first={obj[0] if obj else None}")
    else:
        print(f"{pad}{name}: {obj!r}")


for f in ("s5_split", "fig_data", "eav", "overload_bench",
          "coerce_compare", "master_table"):
    d = json.load(open(R / f"{f}.json"))
    print(f"===== {f}.json =====")
    peek(f, d)

s = json.load(open("results/real_glm53/replay/main_summary.json"))
print("===== main_summary.json (glm53) =====")
peek("summary", s, maxdepth=4)
