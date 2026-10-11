"""Write a driver job: modules of the chosen projects (with their OpenAI import closure) in order."""
import json, pickle, sys
SRC = "/Users/safsom/Projects/math-ai-projects/corpora/openai_math/lean"
info = json.load(open("oai_imports.json"))["mods"]

def project_of(m):
    p = m.split(".")
    return ".".join(p[:3]) if len(p) > 3 else ".".join(p[:2]) + "._root"

def closure(targets):
    seen, order = set(), []
    def visit(m):
        if m in seen: return
        seen.add(m)
        for i in info[m]["imports"]:
            if i.startswith("OAI."): visit(i)
        order.append(m)
    for t in sorted(targets): visit(t)
    return order

def job(projects, out, mathlib_names="", imports=("Mathlib",)):
    P = []
    for p in projects:
        mods = closure([m for m in info if project_of(m) == p])
        P.append(dict(name=p, modules=[dict(mod=m, path=f"{SRC}/{m.replace('.', '/')}.lean") for m in mods]))
    ext = sorted({i for p in P for mj in p["modules"] for i in info[mj["mod"]]["imports"] if not i.startswith("OAI.")})
    imps = sorted(set(imports) | {i for i in ext if i.split(".")[0] in ("Lean", "Std")})
    return dict(out=out, imports=imps, mathlibNames=mathlib_names, projects=P)

if __name__ == "__main__":
    out, names, *projs = sys.argv[1:]
    print(json.dumps(job(projs, out, names)))
