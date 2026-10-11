"""Import graph of OpenAI's Lean library: per-project closure, external roots, size."""
import os, re, json, collections
ROOT = "/Users/safsom/Projects/math-ai-projects/corpora/openai_math/lean"
IMP = re.compile(r"^\s*(?:public\s+)?import\s+(?:all\s+)?([\w.«»']+)", re.M)
mods = {}
for dp, dn, fn in os.walk(os.path.join(ROOT, "OAI")):
    for f in fn:
        if f.endswith(".lean"):
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, ROOT)[:-5]
            src = open(p, encoding="utf-8", errors="replace").read()
            head = src[:20000]
            # imports must precede the first non-import command; take all import lines in the header
            imps = IMP.findall(head.split("\nnamespace")[0].split("\nopen ")[0])
            mods[rel.replace("/", ".")] = dict(imports=imps, lines=src.count("\n"), bytes=len(src))
print("modules", len(mods))
roots = collections.Counter(i.split(".")[0] for m in mods.values() for i in m["imports"])
print(roots.most_common(30))
def proj(m):
    p = m.split(".")
    return ".".join(p[:3]) if len(p) > 3 else ".".join(p[:2]) + "._root"
closure = {}
def clos(m, seen):
    if m in seen: return
    seen.add(m)
    for i in mods.get(m, {}).get("imports", []):
        if i.startswith("OAI."):
            clos(i, seen)
P = collections.defaultdict(list)
for m in mods: P[proj(m)].append(m)
out = []
for p, ms in P.items():
    seen = set()
    for m in ms: clos(m, seen)
    ext = sorted({i.split(".")[0] for s in seen for i in mods.get(s, {}).get("imports", []) if not i.startswith("OAI.")})
    missing = [s for s in seen if s not in mods]
    other_proj = sorted({proj(s) for s in seen} - {p})
    out.append(dict(project=p, n_mod=len(ms), own_lines=sum(mods[m]["lines"] for m in ms),
                    closure_mods=len(seen), closure_lines=sum(mods[s]["lines"] for s in seen if s in mods),
                    ext=ext, other_projects=other_proj, missing=len(missing)))
json.dump(dict(mods=mods, projects=out), open("oai_imports.json", "w"))
import pandas as pd
df = pd.DataFrame(out)
df["ext_ok"] = df.ext.apply(lambda e: set(e) <= {"Mathlib"})
print(df.ext_ok.value_counts())
print(collections.Counter(x for e in df.ext for x in e).most_common(25))
print(df[df.ext_ok].closure_lines.describe())
print("mathlib-only projects with closure<=15000 lines:", (df.ext_ok & (df.closure_lines <= 15000)).sum())
