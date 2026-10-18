"""Compiled-proof analysis: typed gestures, IR energy, linear profile, eigenproofs.

Inputs: out/*.jsonl from the gesture driver. Outputs: out/analysis/*.csv|json.
"""
import collections
import functools
import glob
import json
import math
import os
import pickle
import random
import re
import sys
import zlib

import numpy as np
import pandas as pd
from scipy import linalg, stats

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.environ.get('GOUT', os.path.join(HERE, 'out'))
RES = os.path.join(OUT, os.environ.get('RESNAME', 'analysis'))
MERGE_ARITH = os.environ.get('MERGE_ARITH') == '1'
os.makedirs(RES, exist_ok=True)
MIN_THM = 20
rng = np.random.default_rng(20261010)

# ---------------------------------------------------------------- loading
GENERATED = re.compile(r'\.(eq_\d+|eq_def|injEq|inj|sizeOf_spec|induct|mutual_induct|ext_iff|_.*)$')
INTERNAL = re.compile(r'^(_.*|proof_\d+|match_\d+|eq_\d+|eq_def|_simp_.*|_auxLemma.*)$')


def user_name(n):
    if n.startswith('_private.'):
        parts = n.split('.')
        for i in range(1, len(parts)):
            if parts[i].isdigit():
                return '.'.join(parts[i + 1:])
    return n


def strip_internal(n):
    parts = n.split('.')
    while len(parts) > 1 and INTERNAL.match(parts[-1]):
        parts.pop()
    return '.'.join(parts)


AI_OUT = os.environ.get('AI_OUT', os.path.join(HERE, 'out_ai'))
AI_CORPORA = ['flt', 'spherepacking', 'erdos90', 'putnam2025', 'imo2025']
AI_ROOT = {'flt': '', 'spherepacking': 'SpherePacking', 'erdos90': 'Towers', 'putnam2025': 'Putnam2025',
           'imo2025': 'HarmonicLean'}


def ai_project(corpus, module):
    c = module.split('.')
    if corpus == 'flt':
        # P2M.Sol.S_<Area>_..., Definitions.Def_<Area>_..., P2M.Derive.D_<Area>_...
        stem = c[-1].split('_', 1)[1] if '_' in c[-1] else c[-1]
        return 'flt/' + stem.split('_')[0]
    return corpus + '/' + (c[1] if len(c) > 1 else '_root')


def project_and_group(corpus, module):
    c = module.split('.')
    if corpus in AI_CORPORA:
        return ai_project(corpus, module), corpus
    if corpus == 'mathlib':
        return '/'.join(c[:3]), 'mathlib'
    if corpus == 'openai':
        return '/'.join(c[:3]), 'openai'
    proj = '/'.join(c[:2]) if len(c) > 2 else c[0] + '/_root'
    sub = c[1] if len(c) > 2 else ''
    return proj, ('human-upstream' if sub in ('Mathlib', 'ToMathlib', 'ForMathlib') else 'human')


def compact(r):
    """Coarsen a raw record as soon as it is read (interned strings, merged keys)."""
    u = collections.Counter()
    n_local = n_lemma = 0
    for k, v in r['u'].items():
        u[coarse_i(k)] += v
        if k.startswith('local('):
            n_local += v
        elif k.startswith('lemma('):
            n_lemma += v
    b = collections.Counter()
    for k, v in r['b'].items():
        p, g = k.split('\t')
        b[(p if p == 'ROOT' else coarse_i(p), coarse_i(g))] += v
    atoms = collections.Counter({sys.intern(k): v for k, v in r.get('a', {}).items()})
    return dict(n=r['n'], m=r['m'], p=r.get('p', ''), parent=r.get('parent', r['n']), nodes=r['nodes'],
                tr=r['tr'], sorry=r['sorry'], u=u, b=b, a=atoms, n_local=n_local, n_lemma=n_lemma)


def merge(recs):
    """Merge auxiliary theorems into their source theorem."""
    by = {}
    for r in recs:
        key = r['parent']
        if key in by:
            x = by[key]
            x['u'].update(r['u'])
            x['b'].update(r['b'])
            x['a'].update(r['a'])
            for f in ('nodes', 'n_local', 'n_lemma'):
                x[f] += r[f]
            x['tr'] = x['tr'] or r['tr']
            x['sorry'] = x['sorry'] or r['sorry']
        else:
            by[key] = dict(r, n=key)
    return list(by.values())


HUMAN_REACH = json.load(open(os.path.join(HERE, 'human_reachable.json')))


def load():
    recs = []
    with open(os.path.join(OUT, 'mathlib.jsonl')) as f:
        for line in f:
            r = compact(json.loads(line))
            r['corpus'] = 'mathlib'
            recs.append(r)
    seen = set()
    paths = [(p, None) for p in sorted(glob.glob(os.path.join(OUT, '*.jsonl')))]
    paths += [(p, None) for p in sorted(glob.glob(os.path.join(os.environ.get('HOUT', OUT), 'human.*.jsonl')))]
    if os.environ.get('WITH_AI') == '1':  # other AI corpora (streaming runs, one directory each)
        paths += [(os.path.join(AI_OUT, c, c + '.jsonl'), c) for c in AI_CORPORA
                  if os.path.exists(os.path.join(AI_OUT, c, c + '.jsonl'))]
    for path, ai in paths:
        base = os.path.basename(path)[:-6]
        if base == 'mathlib' or base.endswith('.log') or base.endswith('.trace') or 'partial' in base:
            continue
        corpus = ai or ('human' if base.startswith('human.') else 'openai')
        # human: only modules the library root reaches (what `lake build` compiles)
        reach = set(HUMAN_REACH.get(base, [])) if corpus == 'human' else None
        own_first = []
        for raw in map(json.loads, open(path)):
            u = user_name(raw['n'])
            if GENERATED.search(u) and strip_internal(u) == u:
                continue
            if corpus == 'openai' and raw['p'] != base:
                continue  # theorems of other projects in the closure are taken from their own run
            if reach is not None and raw['m'] not in reach:
                continue
            if corpus == 'flt' and raw['m'].startswith('Theorems.'):
                continue  # statement files: each proof is a one-line wrapper around its P2M.Sol module
            k = (corpus, raw['n'])
            if k in seen:
                continue
            seen.add(k)
            r = compact(raw)
            r['parent'] = strip_internal(u)
            r['corpus'] = corpus
            recs.append(r)
    out = []
    for corpus in ('mathlib', 'openai', 'human', *AI_CORPORA):
        rs = [r for r in recs if r['corpus'] == corpus]
        names = {strip_internal(user_name(r['n'])) for r in rs}
        if corpus != 'mathlib':
            rs = [r for r in rs if r['parent'] in names]
        for r in merge(rs):
            r['project'], r['group'] = project_and_group(corpus, r['m'])
            out.append(r)
    return out


# ---------------------------------------------------------------- gesture coarsening
@functools.lru_cache(maxsize=None)
def coarse_i(g):
    return sys.intern(coarse(g))


def coarse(g):
    if MERGE_ARITH:  # omega and lia/grind certificates as one decision-procedure family
        g = re.sub(r'^tac:(Omega|Grind)', 'tac:IntArith', g)
    g = re.sub(r'^ctor:local\(', 'ctor(', g)
    g = re.sub(r'^def:local\(', 'def(', g)
    g = re.sub(r'^local\(', 'lemma(', g)
    return re.sub(r'P:[A-Za-z]+', 'P', g)


def family(g):
    """Plain-language family of a gesture (for the mix table)."""
    if g.startswith('λh:'):
        return 'assume a hypothesis'
    if g.startswith('λx:'):
        return 'generalize a variable'
    if g.startswith('cut:') or g == 'let':
        return 'state an intermediate claim'
    if g.startswith('hyp('):
        return 'use a hypothesis'
    if g.startswith('core:'):
        name = g[5:g.index('(')] if '(' in g else g[5:]
        if name in ('Eq.mpr', 'Eq.mp', 'congrArg', 'congrFun', 'congr', 'Eq.trans', 'Eq.symm', 'propext',
                    'of_eq_true', 'of_eq_false', 'eq_self', 'eq_true', 'eq_false', 'id', 'Eq.ndrec', 'Eq.rec',
                    'Eq.subst', 'Eq.substr', 'implies_congr', 'forall_congr', 'cast', 'Eq.mpr_prop', 'Eq.mpr_not',
                    'ne_eq', 'iff_of_eq', 'not_false_eq_true', 'funext', 'HEq.refl', 'eq_of_heq', 'heq_of_eq'):
            return 'rewrite along an equation'
        if name in ('Eq.refl', 'rfl', 'HEq.refl', 'trivial', 'True.intro', 'le_refl', 'le_rfl', 'Nat.le.refl',
                    'Iff.refl'):
            return 'close by reflexivity'
        if name in ('Classical.byContradiction', 'Decidable.byContradiction', 'absurd', 'False.elim', 'False.rec',
                    'Not.intro', 'Not.elim', 'mt', 'Function.mt', 'Classical.not_not'):
            return 'argue by contradiction'
        if name in ('Classical.byCases', 'Decidable.byCases', 'Classical.em', 'Or.elim', 'dite', 'ite',
                    'Or.resolve_left', 'Or.resolve_right'):
            return 'split into cases'
        return 'introduce or eliminate a connective'
    if g.startswith('tac:'):
        return 'automation certificate'
    if g.startswith('rec(') or g.startswith('match('):
        return 'induct or pattern-match'
    if g.startswith('decide'):
        return 'decide by computation'
    if g.startswith('lemma(') or g.startswith('local('):
        return 'apply a lemma'
    return 'other'


# ---------------------------------------------------------------- IR energy model
TOK = re.compile(r'[A-Za-z_.:]+|[^\s(),⇒]+|[(),⇒]')


class GestureLM:
    """Interpolated Kneser-Ney model of a child gesture given its parent gesture."""

    def __init__(self, bigrams):
        big = collections.Counter()
        for b in bigrams:
            big.update(b)
        ctx_tot, ctx_types, cont = collections.Counter(), collections.Counter(), collections.Counter()
        for (p, g), c in big.items():
            ctx_tot[p] += c
            ctx_types[p] += 1
            cont[g] += 1
        n1 = sum(1 for c in big.values() if c == 1)
        n2 = sum(1 for c in big.values() if c == 2)
        self.D = n1 / (n1 + 2 * n2) if n1 + 2 * n2 else 0.5
        N = sum(cont.values())
        singletons = sum(1 for c in cont.values() if c == 1)
        self.p_unk = (singletons + 1) / (N + singletons + 1)
        self.p1 = {g: (1 - self.p_unk) * c / N for g, c in cont.items()}
        self.big, self.ctx_tot, self.ctx_types = big, ctx_tot, ctx_types
        toks = collections.Counter()
        for g, c in cont.items():
            toks.update(TOK.findall(g))
        tot = sum(toks.values())
        self.tok_p = {t: c / (tot + len(cont)) for t, c in toks.items()}
        self.tok_stop = len(cont) / (tot + len(cont))
        self.tok_unseen = 0.5 / (tot + len(cont))

    def spell(self, g):
        return sum(-math.log2(self.tok_p.get(t, self.tok_unseen)) for t in TOK.findall(g)) - math.log2(self.tok_stop)

    def bits(self, p, g):
        p1 = self.p1.get(g)
        if p1 is None:
            p1 = self.p_unk * 2.0 ** (-self.spell(g))
        T = self.ctx_tot.get(p, 0)
        if T == 0:
            return -math.log2(p1)
        c = self.big.get((p, g), 0)
        return -math.log2(max(c - self.D, 0) / T + self.D * self.ctx_types[p] / T * p1)


def coarse_bigrams(r):
    out = collections.Counter()
    for k, v in r['b'].items():
        p, g = k.split('\t')
        out[(p if p == 'ROOT' else coarse(p), coarse(g))] += v
    return out


def coarse_unigrams(r):
    out = collections.Counter()
    for k, v in r['u'].items():
        out[coarse(k)] += v
    return out


# ---------------------------------------------------------------- main
def main():
    recs = load()
    D = pd.DataFrame([dict(corpus=r['corpus'], group=r['group'], project=r['project'], name=r['n'],
                           module=r['m'], nodes=r['nodes'], tr=r['tr'], sorry=r['sorry'],
                           n_local=r['n_local'], n_lemma=r['n_lemma']) for r in recs])
    print(D.groupby(['group']).agg(decls=('name', 'size'), sorry=('sorry', 'sum'), tr=('tr', 'sum'),
                                    projects=('project', 'nunique')))
    keep = ~D.sorry.values
    recs = [r for r, k in zip(recs, keep) if k]
    D = D[keep].reset_index(drop=True)
    U = [r['u'] for r in recs]
    BG = [r['b'] for r in recs]

    # ---- IR energy: mathlib held out by project fold (same split as the text channel)
    tp = sorted(set(pd.read_pickle(os.path.join(ROOT, 'energy', 'data', 'text_energy.pkl'))
                    .query("corpus == 'mathlib'").project))
    r7 = random.Random(7)
    r7.shuffle(tp)
    fold_of = {p: i % 5 for i, p in enumerate(tp)}
    # projects outside the text study get a fold from a stable hash of their name
    D['fold'] = [fold_of.get(p, zlib.crc32(p.encode()) % 5) if c == 'mathlib' else -1 for c, p in zip(D.corpus, D.project)]
    E = np.zeros(len(D))
    S = np.zeros(len(D))
    folds = D.fold.to_numpy()
    for f in range(-1, 5):
        tr = [BG[i] for i in range(len(D)) if D.corpus.iat[i] == 'mathlib' and (f == -1 or folds[i] != f)]
        lm = GestureLM(tr)
        idx = np.flatnonzero(folds == f) if f >= 0 else np.flatnonzero(D.corpus.to_numpy() != 'mathlib')
        for i in idx:
            e = s = 0.0
            for (p, g), c in BG[i].items():
                e += c * lm.bits(p, g)
                s += c
            E[i], S[i] = e, s
        print('scored fold', f, len(idx), flush=True)
    D['E_ir'], D['steps'] = E, S

    # ---- linear profile and family mix
    def prof(u):
        h = {m: 0 for m in '01ω'}
        c = {m: 0 for m in '01ω'}
        fam = collections.Counter()
        for g, n in u.items():
            fam[family(g)] += n
            m = re.match(r'λh:.*:([01ω])$', g)
            if m:
                h[m.group(1)] += n
            m = re.match(r'cut:.*:([01ω])$', g)
            if m:
                c[m.group(1)] += n
        return h, c, fam
    H, Cc, F = zip(*[prof(u) for u in U])
    for m in '01ω':
        D[f'hyp_{m}'] = [h[m] for h in H]
        D[f'cut_{m}'] = [c[m] for c in Cc]
    fams = sorted({k for f in F for k in f})
    for k in fams:
        D['fam:' + k] = [f.get(k, 0) for f in F]
    D.to_pickle(os.path.join(RES, 'decls.pkl'))
    pickle.dump(dict(U=U, A=[r.get('a', {}) for r in recs]), open(os.path.join(RES, 'unigrams.pkl'), 'wb'))
    print('saved decls', len(D))


if __name__ == '__main__':
    main()
