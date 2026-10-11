"""Streaming-mode jobs for the other AI-written Lean corpora (run with run_stream.py).

Each corpus is compiled against this repository's mathlib (d13f23b, Lean 4.34.1) in one shared
environment, with its own lakefile's elaboration options. FLT is too large to compile here (60k
modules, 13.5M lines): proof modules are drawn in random order and kept while the union of their
import cones fits in BUDGET lines, so every kept proof is a uniform draw among those whose cone fits.
"""
import json, os, random, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
AI = os.path.join(os.path.dirname(HERE), 'corpora', 'ai')
OUT = os.path.join(HERE, 'out_ai')
IMP = re.compile(r"^\s*(?:public\s+)?import\s+(?:all\s+)?([\w.'«»]+)", re.M)
BUDGET = int(os.environ.get('BUDGET', 800_000))


def scan(root, tops):
    mods = {}
    for top in tops:
        for dp, _, fn in os.walk(os.path.join(root, top)):
            for f in fn:
                if f.endswith('.lean'):
                    p = os.path.join(dp, f)
                    m = os.path.relpath(p, root)[:-5].replace('/', '.')
                    src = open(p, encoding='utf-8', errors='replace').read()
                    head = src
                    cut = re.search(r'^(namespace|section|theorem|lemma|def|open|set_option|noncomputable|variable|/-!)', head, re.M)
                    imps = IMP.findall(head[:cut.start()] if cut else head)
                    mods[m] = dict(path=p, imports=imps, lines=src.count('\n'))
        top_file = os.path.join(root, top + '.lean')
        if os.path.exists(top_file) and top not in mods:
            src = open(top_file, encoding='utf-8', errors='replace').read()
            mods[top] = dict(path=top_file, imports=IMP.findall(src), lines=src.count('\n'))
    for m in mods.values():
        m['deps'] = [i for i in m['imports'] if i in mods]
    return mods


def topo(mods, keep):
    order, seen = [], set()
    def visit(m):
        if m in seen:
            return
        seen.add(m)
        for d in mods[m]['deps']:
            visit(d)
        order.append(m)
    sys.setrecursionlimit(1_000_000)
    for m in sorted(keep):
        visit(m)
    return order


def job(name, mods, order, extra_imports=(), **opts):
    ext = sorted({i for m in order for i in mods[m]['imports'] if i not in mods})
    imports = sorted({'Mathlib'} | set(extra_imports) | {i for i in ext if i.split('.')[0] in ('Lean', 'Std', 'Batteries', 'Aesop', 'Qq', 'Plausible')})
    missing = sorted({i.split('.')[0] for i in ext} - {'Mathlib', 'Lean', 'Std', 'Batteries', 'Aesop', 'Qq', 'Plausible', 'Init', 'ProofWidgets', 'ImportGraph', 'LeanSearchClient'})
    J = dict(out=os.path.join(OUT, name), imports=imports, mathlibNames='', trace=[], isolated=False, oleanDir='',
             maxModules=1_000_000, oleanProjects=[], maxHeartbeats=opts.get('maxHeartbeats', 0),
             synthHeartbeats=opts.get('synthHeartbeats', 0), falseOptions=opts.get('falseOptions', []),
             natOptions=opts.get('natOptions', []), streaming=True,
             projects=[dict(name=name, modules=[dict(mod=m, path=mods[m]['path'], replay=False) for m in order])],
             deps={m: mods[m]['deps'] for m in order})
    json.dump(J, open(os.path.join(HERE, f'job_ai_{name}.json'), 'w'))
    print(f'{name}: {len(order)} modules, {sum(mods[m]["lines"] for m in order):,} lines; imports {imports}; '
          f'unavailable packages {missing}')
    return J


def flt():
    root = os.path.join(AI, 'flt')
    mods = scan(root, ['Definitions', 'Theorems', 'P2M'])
    cone = {}
    def C(m):
        if m not in cone:
            s = {m}
            for d in mods[m]['deps']:
                s |= C(d)
            cone[m] = frozenset(s)
        return cone[m]
    sys.setrecursionlimit(1_000_000)
    sols = sorted(m for m in mods if m.startswith('P2M.Sol.'))
    rng = random.Random(20261010)
    rng.shuffle(sols)
    keep, lines, roots = set(), 0, []
    for s in sols:
        if s in keep:  # already in the cone of an earlier draw
            continue
        new = C(s) - keep
        add = sum(mods[m]['lines'] for m in new)
        if lines + add <= BUDGET:
            keep |= new
            lines += add
            roots.append(s)
    order = topo(mods, keep)
    json.dump(dict(roots=roots, population=len(sols)), open(os.path.join(HERE, 'flt_sample.json'), 'w'))
    print(f'FLT sample: {len(roots)} drawn proof roots of {len(sols)}, '
          f'{sum(m.startswith("P2M.Sol.") for m in keep)} proof modules in their cones')
    return job('flt', mods, order, maxHeartbeats=4_000_000, synthHeartbeats=400_000,
               falseOptions=['backward.isDefEq.respectTransparency.types'])


def simple(name, sub, tops, **opts):
    root = os.path.join(AI, sub)
    mods = scan(root, tops)
    return job(name, mods, topo(mods, set(mods)), **opts)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    flt()
    simple('spherepacking', 'Sphere-Packing-Lean', ['SpherePacking'])
    simple('erdos90', 'Erdos90/src/original', ['Towers'], natOptions=[['maxSynthPendingDepth', 3]])
    simple('putnam2025', 'Putnam2025', ['Putnam2025'])
    simple('imo2025', 'IMO2025', ['HarmonicLean'], natOptions=[['maxSynthPendingDepth', 3]])
