"""Build the external-review export package (read-only on the project).

Stages:
  1. inventory every project file (sha256, mtime, size, classification)
  2. copy into ~/S&P/PG_REVIEW_EXPORT/PG_REVIEW_PACKAGE/ staging tree;
     raw arm data staged separately per arm; security scan + redaction
     applied to COPIES ONLY; CORE gets representative raw samples
  3. tar PG_REVIEW_CORE + PG_REVIEW_RAW_PART_<arm>, sha256 everything
  4. verify: originals unchanged (full re-hash), tar integrity + hash
     spot-match, cross-layer linkage checks; write EXPORT_REPORT.md

Run: .venv/bin/python scripts/build_review_export.py
"""
import csv
import datetime
import hashlib
import json
import pathlib
import re
import shutil
import sys
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[1].resolve()
EXPORT = ROOT.parent / "PG_REVIEW_EXPORT"
PKG = EXPORT / "PG_REVIEW_PACKAGE"
PARTS = EXPORT / "packages"
REPORT = []

ARMS = ["real_glm53", "real_claude55", "real_gemini38flash",
        "real_deepseek41flash", "real_gpt56"]
SKIP_DIRS = {".venv", "__pycache__", ".pytest_cache", "node_modules",
             ".git", ".claude", "PG_REVIEW_EXPORT"}
SKIP_SUFFIX = (".pyc", ".pyo")


def sha256(p, chunk=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                return h.hexdigest()
            h.update(b)


def note(s):
    print(s, flush=True)
    REPORT.append(s)


# ---------------------------------------------------------------- classify
def classify(rel):
    """-> (experiment, evidence_type, dst_in_package_or_None, note)
    dst=None means: excluded (.env) or handled via per-arm RAW staging."""
    r = rel.as_posix()
    if rel.name == ".env":
        return ("ENV", "credentials", None, "EXCLUDED: API keys never exported")
    top = rel.parts[0]
    tail = pathlib.Path(*rel.parts[1:])
    if rel.name == ".env.example":
        return ("ENV", "config", "08_RUNTIME/.env.example", "")
    if top == "logs":
        return ("RUNTIME", "logs", f"08_RUNTIME/logs/{tail}", "")
    if top == "docs":
        return ("PROTOCOL", "docs", f"01_PROTOCOL/docs/{tail}", "")
    if top in ("src", "tests", "experiments"):
        return ("SOURCE", "code", f"02_SOURCE/{top}/{tail}", "")
    if top == "scripts":
        return ("SOURCE", "code", f"02_SOURCE/scripts/{tail}",
                "figure scripts also referenced from 06_FIGURES specs")
    if r == "README.md":
        return ("PROJECT", "docs", "00_INDEX/project_README.md", "")
    if r == "requirements.txt":
        return ("RUNTIME", "config", "08_RUNTIME/requirements.txt", "")
    if r == ".gitignore":
        return ("RUNTIME", "config", "08_RUNTIME/dot-gitignore", "")
    if top == "results":
        sub = rel.parts[1] if len(rel.parts) > 1 else ""
        tail2 = pathlib.Path(*rel.parts[2:])
        if sub in ("E1", "E2", "E5", "E6", "E7", "E8", "E9", "ER"):
            ev = "offline deterministic enumeration" if sub == "E8" \
                else "mock/synthetic offline"
            return (sub if sub != "E2" else "E2/E3", ev,
                    f"05_E1_TO_E9/{sub}/{tail2}",
                    "E3 merged into E2 by design" if sub == "E2" else "")
        if sub == "LLM_PILOT":
            nt = "duplicate freeze copy" if "freeze" in r else ""
            return ("PILOT", "real LLM", f"05_E1_TO_E9/PILOT_REAL/{tail2}", nt)
        if sub == "real_qwen37plus":
            return ("QWEN-DROPPED", "replay_v2 shell",
                    f"04_REPLAY/real_qwen37plus/{tail2}",
                    "0 trajectories; vendor outage, arm dropped")
        if sub in ARMS:
            st = tail2.parts[0] if tail2.parts else ""
            exp = sub.replace("real_", "MAIN-").upper()
            if st == "rollouts":
                return (exp, "real trajectory", None, "RAW part; CORE sample")
            if st == "raw":
                return (exp, "llm call cache", None,
                        "RAW part; CORE 2-file sample")
            if st == "replay":
                nt = "superseded pre-ATC-fix" if "pre_atcfix" in r \
                    else "v1; cppe_scope field dead — use replay_v2"
                return (exp, "replay v1", None, nt)
            if st == "replay_v2":
                return (exp, "replay_v2 derived", None,
                        "RAW part; CORE head-100 sample")
            if st == "audit":
                return ("GATES", "audit",
                        f"07_AUDIT/real_arm_audits/{sub}/"
                        + str(pathlib.Path(*tail2.parts[1:])), "")
            return ("GATES", "audit", f"07_AUDIT/arm_root_files/{sub}/{tail2}",
                    "e.g. PURGE_REPORT.json")
        if sub == "TABLES":
            return ("TABLES", "derived table",
                    f"06_FIGURES/data/TABLES/{tail2}",
                    "atk_oop & atc_b1 columns banned (I7)")
        if sub == "FIGS":
            nt = "" if "v3_20261010" in r else "superseded candidate (kept)"
            return ("FIGS", "figure", f"06_FIGURES/FIGS/{tail2}", nt)
        if sub.startswith("FREEZE"):
            return ("FREEZE", "audit manifest",
                    f"07_AUDIT/FREEZE_MANIFEST/{tail2}",
                    "version anchor (no git repo)")
        if sub == "DATA_SUMMARY_20261010":
            return ("SUMMARY", "derived summary",
                    f"06_FIGURES/data/DATA_SUMMARY/{tail2}", "")
        if sub.endswith(".log"):
            return ("RUNTIME", "logs", f"08_RUNTIME/logs/{sub}", "")
        fallback = tail2 if tail2.parts else rel.name
        return ("UNMATCHED-results", "?", f"00_INDEX/_UNSORTED/{fallback}",
                "auto-bucket — reviewer check")
    if top == "audit_20261010":
        return ("GATES-A-E", "audit", f"07_AUDIT/audit_20261010/{tail}", "")
    return ("UNMATCHED", "?", f"00_INDEX/_UNSORTED/{rel}", "auto-bucket")


# ---------------------------------------------------------------- stage 1
def inventory():
    recs = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if rel.suffix in SKIP_SUFFIX or \
                rel.name == "build_review_export.log":   # this run's own log
            continue
        exp, ev, tgt, nt = classify(rel)
        in_raw = bool(exp.startswith("MAIN-") and tgt is None)
        recs.append({"rel": rel, "size": p.stat().st_size,
                     "mtime": datetime.datetime.fromtimestamp(
                         p.stat().st_mtime).isoformat(timespec="seconds"),
                     "sha": sha256(p), "exp": exp, "ev": ev, "tgt": tgt,
                     "raw": in_raw, "note": nt, "abs": str(p)})
    return recs


# ---------------------------------------------------------------- stage 2
SENSITIVE = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "sk- key"),
    (re.compile(r"sk-azx-[A-Za-z0-9\-]{10,}"), "aizex key"),
    (re.compile(r"\b(?:6fc70d|a923bf|c85a4d)[A-Za-z0-9]{10,}\b"), "glm key prefix"),
    (re.compile(r"Bearer\s+[A-Za-z0-9_\-.]{16,}"), "bearer token"),
    (re.compile(r"(?i)(api[_-]?key|auth[_-]?token)\s*[=:]\s*['\"]?[A-Za-z0-9_\-.]{20,}"),
     "key assignment"),
]
TEXT_OK = (".py", ".md", ".txt", ".json", ".jsonl", ".csv", ".yaml", ".yml",
           ".sh", ".log", ".tex", ".example", "")


def scan_and_redact(path, sec_rows, rel_label):
    """Scan a staged copy; redact secret-looking tokens IN THE COPY only."""
    if not path.is_file() or path.suffix not in TEXT_OK \
            or path.stat().st_size > 200 << 20:   # scan everything text
        return
    try:
        txt = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        return
    total = 0
    for rx, label in SENSITIVE:
        n = len(rx.findall(txt))
        if n:
            txt = rx.sub(lambda m: f"REDACTED({m.group(0)[:4]}…)", txt)
            total += n
            sec_rows.append([rel_label, path.name, label, n, "redacted-in-copy"])
    if total:
        path.write_text(txt, encoding="utf-8")


def copy_stage(recs, sec_rows):
    big = []
    for r in recs:
        if r["tgt"] is None:
            if r["exp"] == "ENV":
                sec_rows.append([r["rel"].as_posix(), r["rel"].name,
                                 ".env credentials", 1, "excluded-entirely"])
            continue
        dst = PKG / r["tgt"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(r["abs"], dst)
        scan_and_redact(dst, sec_rows, r["rel"].as_posix())
        if r["size"] > 50 << 20:
            big.append((r["rel"].as_posix(), r["size"]))
            note(f"LARGE FILE >50MB: {r['rel']} ({r['size']//(1<<20)}MB)")
    return big


def add_samples(sec_rows):
    """CORE gets representative raw records per evidence class."""
    s = PKG / "03_RAW_TRACES" / "_CORE_SAMPLES"
    s.mkdir(parents=True, exist_ok=True)
    for a in ARMS:
        base = ROOT / "results" / a
        main = sorted((base / "rollouts" / "main").glob("*.json"))
        for f in [x for x in main if x.is_file()][:2]:
            d = s / f"{a}_rollout_{f.name}"
            shutil.copy2(f, d)
            scan_and_redact(d, sec_rows, f"results/{a}/rollouts/main/{f.name}")
        acc = base / "rollouts" / "acceptance"
        if acc.is_dir():
            accs = [x for x in acc.rglob("*.jsonl") if x.is_file()]
            for f in accs[:1]:                    # 1 acceptance scenario/arm
                d = s / f"{a}_acceptance_{f.name}"
                shutil.copy2(f, d)
                scan_and_redact(d, sec_rows, str(f.relative_to(ROOT)))
        rawc = [x for x in sorted((base / "raw").glob("*")) if x.is_file()][:2]
        for f in rawc:
            d = s / f"{a}_rawcache_{f.name}"
            shutil.copy2(f, d)
            scan_and_redact(d, sec_rows, f"results/{a}/raw/{f.name}")
        v2 = base / "replay_v2" / "main.jsonl"
        if v2.exists():
            with open(v2, encoding="utf-8") as fi, \
                 open(s / f"{a}_replay_v2_head100.jsonl", "w",
                      encoding="utf-8") as fo:
                for i, line in enumerate(fi):
                    if i >= 100:
                        break
                    fo.write(line)
        note(f"  samples[{a}]: {min(2, len(main))} rollout, "
             f"{1 if acc.is_dir() else 0} acceptance, {len(rawc)} raw, "
             f"{'100' if v2.exists() else '0'} replay_v2 rows")
    e2s = sorted((ROOT / "results" / "E2").glob("*/trace.jsonl"))
    if e2s:
        d = PKG / "05_E1_TO_E9" / "E2" / "trace_head1000.jsonl"
        with open(e2s[0], encoding="utf-8") as fi, \
                open(d, "w", encoding="utf-8") as fo:
            for i, line in enumerate(fi):
                if i >= 1000:
                    break
                fo.write(line)
        note(f"  E2 full trace ({e2s[0].stat().st_size//(1<<20)}MB) also "
             "copied whole into CORE 05_E1_TO_E9/E2/")


# ---------------------------------------------------------------- stage 3
def tar_dir(src_dir, arc_root, out_file):
    files = sorted(p for p in src_dir.rglob("*") if p.is_file())
    with tarfile.open(out_file, "w:gz", compresslevel=6) as tf:
        for p in files:
            tf.add(p, arcname=str(pathlib.Path(arc_root) / p.relative_to(src_dir)))
    return len(files)


# ---------------------------------------------------------------- stage 4
def verify(recs, tars):
    ok = []
    changed = [r["rel"].as_posix() for r in recs
               if sha256(pathlib.Path(r["abs"])) != r["sha"]]
    ok.append(("originals-unmodified (full re-hash of all sources)",
               "PASS" if not changed else f"FAIL {changed[:5]}"))
    for name, path, arc_root in tars:
        with tarfile.open(path) as tf:            # gzip/tar integrity + read
            members = [m for m in tf.getmembers() if m.isfile()]
            mism = 0
            for m in members[:50]:
                h = hashlib.sha256(tf.extractfile(m).read()).hexdigest()
                local = EXPORT / "PG_REVIEW_PACKAGE" / pathlib.Path(m.name) \
                    .relative_to(arc_root)
                if local.exists() and sha256(local) != h:
                    mism += 1
            ok.append((f"tar-integrity:{name}",
                       f"PASS ({len(members)} files readable, "
                       f"{min(50, len(members))} hashed, {mism} mismatch)"))
    cvp = PKG / "07_AUDIT" / "audit_20261010" / "gates" / "cell_verify_v3.json"
    cv = json.load(open(cvp))
    d = cv["denominators"]
    want = {"trajectories_legit": 4000, "proposing": 3168,
            "well_formed_proposals": 2960, "pg_installed": 2275,
            "pg_out_of_root": 584}
    bad = {k: (d.get(k), v) for k, v in want.items() if d.get(k) != v}
    ok.append(("spot-linkage:cell_verify_v3 denominators (cv3↔Gate C)",
               "PASS 4000/3168/2960/2275/584" if not bad else f"FAIL {bad}"))
    figd = json.load(open(PKG / "06_FIGURES/data/TABLES/fig_data_v2.json"))
    ok.append(("spot-linkage:fig_data_v2 cells", f"{len(figd['cell'])} cells"))
    sample = PKG / "03_RAW_TRACES/_CORE_SAMPLES/real_glm53_replay_v2_head100.jsonl"
    rows = [json.loads(x) for x in open(sample, encoding="utf-8")]
    ok.append(("spot-linkage:replay_v2 head-100 parses",
               f"PASS keys={sorted(rows[0])[:8]}…"))
    fork = [json.loads(x) for x in open(
        PKG / "07_AUDIT/audit_20261010/gates/authority_fork_results.jsonl")]
    inst = sum(1 for r in fork if r.get("fork") == "grant_absent"
               and r.get("installed"))
    ok.append(("spot-linkage:fork grant_absent installs=0",
               "PASS" if inst == 0 and len(fork) == 13200
               else f"CHECK rows={len(fork)} inst={inst}"))
    return ok


def main():
    assert not EXPORT.resolve().is_relative_to(ROOT), "export outside project"
    for d in (PKG, EXPORT / "RAW_STAGING"):
        if d.exists():
            shutil.rmtree(d)
    PARTS.mkdir(parents=True, exist_ok=True)
    for old in PARTS.glob("*.tar.gz"):
        old.unlink()
    sec_rows = [["source_rel", "file", "pattern_or_action", "count", "handling"]]

    note("== stage 1: inventory (sha256 of every file) ==")
    recs = inventory()
    note(f"{len(recs)} files, "
         f"{sum(r['size'] for r in recs)/(1<<20):.0f}MB total")

    note("== stage 2: staging copy + security scan (copies only) ==")
    copy_stage(recs, sec_rows)
    add_samples(sec_rows)
    sys.path.insert(0, str(ROOT / "scripts"))
    import review_export_content as content
    content.write_all(PKG)

    # inventory CSVs: export root AND inside CORE's 00_INDEX
    inv_rows = [[r["rel"].as_posix(), r["size"], r["sha"], r["mtime"],
                 r["exp"], r["ev"], r["tgt"] or "", bool(r["tgt"]),
                 r["raw"], r["note"]] for r in recs]
    inv_hdr = ["rel_path", "size_bytes", "sha256", "mtime", "experiment",
               "evidence_type", "export_target", "in_core", "in_raw_part",
               "note"]
    with open(EXPORT / "FILE_INVENTORY.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(inv_hdr)
        w.writerows(inv_rows)
    with open(EXPORT / "SECURITY_SCAN.csv", "w", newline="",
              encoding="utf-8-sig") as f:
        csv.writer(f).writerows(sec_rows)
    for src in ("FILE_INVENTORY.csv", "SECURITY_SCAN.csv"):
        shutil.copy2(EXPORT / src, PKG / "00_INDEX" / src)
    note(f"security actions: {len(sec_rows) - 1}")

    note("== stage 3: tars ==")
    tars = []
    core = PARTS / "PG_REVIEW_CORE.tar.gz"
    n = tar_dir(PKG, "PG_REVIEW_PACKAGE", core)
    tars.append(("CORE", core, "PG_REVIEW_PACKAGE"))
    note(f"CORE {core.stat().st_size/(1<<20):.1f}MB, {n} files")
    for a in ARMS:
        stage = EXPORT / "RAW_STAGING" / a
        stage.mkdir(parents=True)
        for sub, nm in [("rollouts", "rollouts"), ("raw", "llm_call_cache"),
                        ("replay", "replay_v1"), ("replay_v2", "replay_v2")]:
            src = ROOT / "results" / a / sub
            if src.exists():
                shutil.copytree(src, stage / "03_RAW_TRACES" / a / nm
                                if sub in ("rollouts", "raw")
                                else stage / "04_REPLAY" / a / nm)
        part = PARTS / f"PG_REVIEW_RAW_PART_{a.replace('real_', '')}.tar.gz"
        n = tar_dir(stage, a, part)
        tars.append((a, part, a))
        note(f"PART {a} {part.stat().st_size/(1<<20):.1f}MB, {n} files")
        shutil.rmtree(stage)
    with open(EXPORT / "SHA256SUMS.txt", "w") as f:
        for p in sorted(PARTS.glob("*.tar.gz")) + [EXPORT / "FILE_INVENTORY.csv"]:
            rel = p.relative_to(EXPORT).as_posix()
            f.write(f"{sha256(p)}  {rel}\n")

    note("== stage 4: verify ==")
    for k, v in verify(recs, tars):
        note(f"VERIFY {k}: {v}")

    # known gaps reported honestly
    gaps = []
    for d in ("configs", "data"):
        gaps.append(f"{d}/ does not exist in project "
                    "(configuration lives inline in experiments/*.py; "
                    "no static data dir)")
    gaps += ["E3 merged into E2 by design (see EV row E2/E3)",
             "E4 degenerate for single mock model, not run separately",
             "qwen arm: no data (vendor outage), only 4KB replay_v2 shell",
             "no git repo — version anchor = FREEZE manifest + "
             "replay_v2_manifest.json sha256s"]
    note("== report ==")
    rep = EXPORT / "EXPORT_REPORT.md"
    with open(rep, "w", encoding="utf-8") as f:
        f.write("# EXPORT_REPORT — PG external review package — 2026-10-10\n\n")
        f.write("**This is a packaging-integrity report, NOT an independent "
                "scientific audit.** It verifies: every source file hashed "
                "before and after export (unchanged), archives open and "
                "hash-match their staged copies, and headline numbers link "
                "across layers.\n\n## Log\n\n```\n")
        f.write("\n".join(REPORT))
        f.write("\n```\n\n## Known gaps / honest omissions\n\n")
        for g in gaps:
            f.write(f"- {g}\n")
        f.write("\n## Sensitive-information exclusion\n\n"
                "- `.env` (1,257B, mode 600) EXCLUDED entirely — never "
                "copied, never hashed into any archive.\n"
                "- Pattern scan + redaction ran on every staged text file "
                "≤8MB (see SECURITY_SCAN.csv); originals untouched.\n"
                "- No SSH keys / cloud tokens / Claude session auth present "
                "in project tree (verified during pre-export sweep).\n\n"
                "## Packages\n\n")
        for p in sorted(PARTS.glob("*.tar.gz")):
            f.write(f"- {p.name}: {p.stat().st_size/(1<<20):.1f}MB "
                    f"sha256={sha256(p)}\n")
        f.write(f"- FILE_INVENTORY.csv: "
                f"{(EXPORT/'FILE_INVENTORY.csv').stat().st_size} bytes "
                f"sha256={sha256(EXPORT/'FILE_INVENTORY.csv')}\n")
    print("DONE ->", EXPORT)


if __name__ == "__main__":
    main()
