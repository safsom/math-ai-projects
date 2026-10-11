"""Compile selected OpenAI projects against the built mathlib (d13f23b, Lean v4.34.1).

Modules are elaborated with plain `lean -o` in dependency order, several at a time, each with a timeout.
Usage: python3 build_oai.py PROJECT [PROJECT ...]     (project = OAI.Area.Topic)
Writes build/<module path>.olean and build/log.jsonl (one record per module).
"""
import json
import os
import subprocess
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "/Users/safsom/Projects/math-ai-projects/corpora/openai_math/lean"
OUT = os.path.join(HERE, "build")
LEAN = os.path.expanduser("~/.elan/toolchains/leanprover--lean4---v4.34.1/bin/lean")
ML = "/Users/safsom/Projects/math-ai-projects/mathlib4"
PKGS = ["Cli", "batteries", "Qq", "aesop", "proofwidgets", "importGraph", "LeanSearchClient", "plausible"]
LEAN_PATH = ":".join([f"{ML}/.lake/packages/{p}/.lake/build/lib/lean" for p in PKGS]
                     + [f"{ML}/.lake/build/lib/lean", OUT])
JOBS = int(os.environ.get("JOBS", 3))
TIMEOUT = int(os.environ.get("TIMEOUT", 1800))

info = json.load(open(os.path.join(HERE, "oai_imports.json")))["mods"]


def project_of(m):
    p = m.split(".")
    return ".".join(p[:3]) if len(p) > 3 else ".".join(p[:2]) + "._root"


def closure(targets):
    seen, order = set(), []

    def visit(m):
        if m in seen:
            return
        seen.add(m)
        for i in info[m]["imports"]:
            if i.startswith("OAI."):
                visit(i)
        order.append(m)
    for t in targets:
        visit(t)
    return order


def olean(m):
    return os.path.join(OUT, *m.split(".")) + ".olean"


def compile_one(m):
    out = olean(m)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    src = os.path.join(SRC, *m.split(".")) + ".lean"
    t = time.time()
    try:
        r = subprocess.run([LEAN, "-DautoImplicit=false", f"--root={SRC}", "-o", out, src],
                           env={**os.environ, "LEAN_PATH": LEAN_PATH}, capture_output=True, text=True,
                           timeout=TIMEOUT)
        ok = r.returncode == 0
        msg = (r.stdout + r.stderr)[-2000:]
    except subprocess.TimeoutExpired:
        ok, msg = False, "timeout"
    if not ok and os.path.exists(out):
        os.remove(out)
    return dict(module=m, ok=ok, seconds=round(time.time() - t, 1), msg="" if ok else msg)


def build(projects):
    targets = [m for m in info if project_of(m) in set(projects)]
    order = closure(targets)
    todo = [m for m in order if not os.path.exists(olean(m))]
    deps = {m: [i for i in info[m]["imports"] if i.startswith("OAI.")] for m in todo}
    done = {m for m in order if os.path.exists(olean(m))}
    failed = set()
    log = open(os.path.join(OUT, "log.jsonl"), "a")
    print(f"{len(targets)} target modules, {len(order)} in closure, {len(todo)} to build", flush=True)
    running = {}
    with ThreadPoolExecutor(JOBS) as ex:
        while todo or running:
            for m in list(todo):
                if len(running) >= JOBS:
                    break
                if any(d in failed for d in deps[m]):
                    failed.add(m)
                    todo.remove(m)
                    log.write(json.dumps(dict(module=m, ok=False, seconds=0, msg="dependency failed")) + "\n")
                    continue
                if all(d in done for d in deps[m]):
                    todo.remove(m)
                    running[ex.submit(compile_one, m)] = m
            if not running:
                break
            fin, _ = wait(running, return_when=FIRST_COMPLETED)
            for f in fin:
                m = running.pop(f)
                r = f.result()
                (done if r["ok"] else failed).add(m)
                log.write(json.dumps(r) + "\n")
                log.flush()
                print(("ok  " if r["ok"] else "FAIL"), f"{r['seconds']:7.1f}s", m, flush=True)
    print(f"built {len(done)} failed {len(failed)}", flush=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    build(sys.argv[1:])
