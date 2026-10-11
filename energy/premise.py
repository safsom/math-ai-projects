"""Premise energy: the code length of the global constants a declaration refers to, under
mathlib's own reference distribution.

Identifiers are resolved syntactically (namespaces, `open`s, `_root_`) against
  * the elaborated mathlib environment at OpenAI's pinned revision (data/mathlib_env.tsv), which
    includes generated names (structure projections, constructors, to_additive, simps lemmas), and
  * the names each corpus declares itself.
Binder-position identifiers are excluded so local variables are not mistaken for constants.

Two-part code per resolved reference r in a declaration of project P:
  library  r = c in mathlib:   -log2(1 - pi_b) - log2 q(c),
                               q(c) = (n_c + a) / (N + a |C|) from mathlib's syntactic reference counts
  bespoke  r defined outside:  -log2 pi_b - log2 (1 / m),  m = names visible in that scope
                               (own project if r is declared there, else the corpus' other names)
pi_b is mathlib's own rate of same-project references. mathlib declarations are scored with counts that
exclude their own fold, exactly as in the text channel.
"""
import math
import pickle
import random
import re
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from lexer import tokenize

ALPHA = 0.5
CORPORA = ['mathlib', 'openai', 'tenproofs', 'carleson', 'flt', 'pfr', 'sphere', 'strongpnt']
# OpenAI's library depends on these corpora, so their names are visible from OAI code.
DEPS = {'openai': ['carleson', 'strongpnt', 'sphere'], 'tenproofs': []}

BINDER_LEAD = {"fun", "λ", "∀", "∃", "∃!", "intro", "intros", "rintro", "obtain", "have", "let", "set",
               "with", "⟨", "|", "case", "next", "generalize", "induction", "cases", "rcases", "refine",
               "by_contra", "by_cases", "choose", "use", "lift", "ext", "funext", "congr", "calc", "show"}
OPEN_BR = {"(", "{", "⦃", "["}


def idents_and_binders(text):
    toks = list(tokenize(text))
    binders = set()
    ids = []
    i = 0
    n = len(toks)
    while i < n:
        k, t = toks[i]
        if k == "op" and t in OPEN_BR or (k == "id" and t in BINDER_LEAD) or (k == "op" and t in ("⟨", "|", "∀", "∃", "λ")):
            j = i + 1
            while j < n and (toks[j][0] == "id" and "." not in toks[j][1] or toks[j][1] in (",", "⟨", "⟩", "-", "_", "@")):
                if toks[j][0] == "id":
                    binders.add(toks[j][1])
                j += 1
            # a bracket group is a binder only if a ':' (or ':=' for have) follows the names
            if k == "op" and t in OPEN_BR and not (j < n and toks[j][1] in (":", ":=")):
                for jj in range(i + 1, j):
                    if toks[jj][0] == "id":
                        binders.discard(toks[jj][1])
        if k == "id":
            ids.append(t)
        i += 1
    return [x for x in ids if x not in binders and x.split(".")[0] not in binders]


def load_env():
    env = pd.read_csv('data/mathlib_env.tsv', sep='\t', header=None, quoting=3,
                      names=['name', 'module', 'kind', 'internal', 'elab_uses'], keep_default_na=False)
    env = env[env.internal == 0]
    return set(env.name), env


def candidates(ident, namespace, opens):
    if ident.startswith("_root_."):
        yield ident[7:]
        return
    ns = list(namespace)
    for k in range(len(ns), -1, -1):
        yield ".".join(ns[:k] + [ident])
    for o in opens:
        yield f"{o}.{ident}"


def resolve(ident, d, mathlib_names, proj_names, corpus_names):
    """Return ('lib'|'local'|'other', fullname) or None."""
    for c in candidates(ident, d['namespace'], d['opens']):
        if c in proj_names:
            return 'local', c
        if c in corpus_names:
            return 'other', c
        if c in mathlib_names:
            return 'lib', c
    return None


def main():
    mathlib_names, env = load_env()
    data = {c: pickle.load(open(f'data/decls_{c}.pkl', 'rb')) for c in CORPORA}
    # names declared per project, and per corpus (+ dependencies)
    proj_names = {}
    corpus_names = {}
    for c, blob in data.items():
        allc = set()
        for p, nm in blob['names'].items():
            proj_names[(c, p)] = set(nm)
            allc.update(nm)
        corpus_names[c] = allc
    for c, deps in DEPS.items():
        for dep in deps:
            corpus_names[c] = corpus_names[c] | corpus_names[dep]

    # Pass 1: resolve every sampled declaration.
    refs = []  # (corpus, project, decl_idx, cls, name)
    meta = []
    unresolved = []
    for c in CORPORA:
        for d in data[c]['decls']:
            i = len(meta)
            meta.append((c, d['project'], d['full'], d['kind'], d['cert']))
            pn = proj_names[(c, d['project'])]
            # for mathlib, other mathlib projects ARE the library
            cn = set() if c == 'mathlib' else corpus_names[c]
            nu = 0
            for ident in idents_and_binders(d['statement'] + " := " + d['proof']):
                r = resolve(ident, d, mathlib_names, pn, cn)
                if r is None:
                    nu += 1
                    continue
                cls, full = r
                refs.append((i, cls, full))
            unresolved.append(nu)
    R = pd.DataFrame(refs, columns=['decl', 'cls', 'name'])
    M = pd.DataFrame(meta, columns=['corpus', 'project', 'full', 'kind', 'cert'])
    M['n_unresolved'] = unresolved

    # mathlib fold assignment (same split as the text channel)
    mp = sorted(M.loc[M.corpus == 'mathlib', 'project'].unique())
    rng = random.Random(7)
    rng.shuffle(mp)
    fold = {p: i % 5 for i, p in enumerate(mp)}
    M['fold'] = [fold.get(p, -1) if c == 'mathlib' else -1 for c, p in zip(M.corpus, M.project)]
    R = R.merge(M[['corpus', 'project', 'fold']], left_on='decl', right_index=True)

    # Reference model from mathlib's own syntactic references.
    # In mathlib, a 'local' reference (same project) is a library constant seen from elsewhere too:
    # q(c) counts every mathlib reference to c, from any project.
    ml = R[R.corpus == 'mathlib']
    C = len(mathlib_names)
    counts_all = Counter(ml.name)
    counts_fold = [Counter(ml[ml.fold == f].name) for f in range(5)]
    N_all = sum(counts_all.values())
    pi_b_all = (ml.cls == 'local').mean()
    pi_b_fold = [(ml[ml.fold != f].cls == 'local').mean() for f in range(5)]
    print(f"mathlib refs {N_all}, same-project share pi_b = {pi_b_all:.4f}, |C| = {C}")

    proj_size = {k: max(1, len(v)) for k, v in proj_names.items()}
    corp_size = {c: max(1, len(v)) for c, v in corpus_names.items()}
    N_fold = [N_all - sum(cf.values()) for cf in counts_fold]
    # q(c): mathlib reference frequency, held-out fold counts for mathlib declarations
    cnt = R.name.map(counts_all).fillna(0).to_numpy(float)
    isml = (R.fold >= 0).to_numpy()
    for f in range(5):
        m = (R.fold == f).to_numpy()
        cnt[m] -= R.name[m].map(counts_fold[f]).fillna(0).to_numpy(float)
    N = np.where(isml, np.take(N_fold, R.fold.clip(lower=0)), N_all)
    pi_b = np.where(isml, np.take(pi_b_fold, R.fold.clip(lower=0)), pi_b_all)
    in_ml = R.name.isin(mathlib_names).to_numpy()
    q = np.where(in_ml, (cnt + ALPHA) / (N + ALPHA * C), 0.0)
    # bespoke component: uniform over the names visible in the reference's scope
    m_scope = np.array([proj_size[(c, p)] if cl == 'local' else corp_size[c]
                        for c, p, cl in zip(R.corpus, R.project, R.cls)], dtype=float)
    bespoke = (R.cls != 'lib').to_numpy()
    p = (1 - pi_b) * q + np.where(bespoke, pi_b / m_scope, 0.0)
    bits = -np.log2(p)
    lib_bits = np.where(in_ml & ~bespoke, -np.log2((1 - pi_b) * q + 1e-300), np.nan)
    R['bits'] = bits
    R['lib_bits'] = lib_bits
    g = R.groupby('decl')
    M['E_prem'] = g.bits.sum()
    M['n_ref'] = g.size()
    M['n_lib'] = g.lib_bits.count()
    M['n_bespoke'] = M.n_ref - M.n_lib
    M['E_libsurp'] = g.lib_bits.sum()
    M[['E_prem', 'n_ref', 'n_lib', 'n_bespoke', 'E_libsurp']] = M[['E_prem', 'n_ref', 'n_lib', 'n_bespoke', 'E_libsurp']].fillna(0)
    M.to_pickle('data/premise_energy.pkl')
    s = M.groupby('corpus')[['E_prem', 'n_ref', 'n_lib', 'n_unresolved']].sum()
    s['bits_per_ref'] = s.E_prem / s.n_ref
    s['lib_share'] = s.n_lib / s.n_ref
    print(s)


if __name__ == '__main__':
    main()
