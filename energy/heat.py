"""Per-token surprisal for a few example declarations, for the report's heat-mapped proofs.

Examples: OpenAI core theorems (40-90 tokens) at the 2nd, 50th and 98th percentile of specific energy,
plus a held-out mathlib theorem at its median. Output: data/out/heat.json
"""
import json
import math
import pickle
import random

import numpy as np
import pandas as pd

from kn import KN, PAD, UNK, Encoded, Vocab
from lexer import TOKEN_RE, LONGNUM_DIGITS, literal_bits, split_ident

ORDER = 5
T = pd.read_pickle('data/text_energy.pkl')
T['e'] = T.E_struct / T.n_tok
m = pickle.load(open('data/decls_mathlib.pkl', 'rb'))['decls']
o = pickle.load(open('data/decls_openai.pkl', 'rb'))['decls']


def pick(df, q, corpus):
    sub = df[(df.corpus == corpus) & df.kind.isin(['theorem', 'lemma']) & ~df.cert & df.n_tok.between(45, 90)]
    v = sub.e.quantile(q)
    return sub.iloc[(sub.e - v).abs().argsort()[:1]].iloc[0]


rows = [('OpenAI, low energy', pick(T, .05, 'openai')), ('OpenAI, median', pick(T, .5, 'openai')),
        ('OpenAI, high energy', pick(T, .95, 'openai')), ('mathlib (held out), median', pick(T, .5, 'mathlib'))]


def find(decls, r):
    for d in decls:
        if d['project'] == r.project and d['full'] == r.full and d['kind'] == r.kind:
            return d


projs = sorted({d['project'] for d in m})
rng = random.Random(7)
rng.shuffle(projs)
fold = {p: i % 5 for i, p in enumerate(projs)}
out = []
models = {}
for label, r in rows:
    d = find(m if r.corpus == 'mathlib' else o, r)
    f = fold[r.project] if r.corpus == 'mathlib' else -1
    if f not in models:
        tr = [x for x in m if fold[x['project']] != f] if f >= 0 else m
        voc = Vocab(tr)
        models[f] = (voc, KN(Encoded(tr, voc, ORDER), ORDER))
    voc, M = models[f]
    enc = Encoded([d], voc, ORDER)
    idx, bits = M.logprob2(enc)
    toks = enc.toks[idx]
    # rebuild display spans: walk the source tokens, attributing piece bits to each surface token
    spans = []
    seen = {}  # within-declaration reuse only (the project-level state is not replayed here)
    k = 0
    pieces_bits = list(bits[:-1])  # last position is end-of-declaration
    unk_flags = list(toks[:-1] == UNK)
    for src in (d['statement'], d['proof']):
        pos = 0
        for mt in TOKEN_RE.finditer(src):
            if mt.start() > pos:
                spans.append([src[pos:mt.start()], None])
            kind = mt.lastgroup
            t = mt.group(kind)
            n = len(split_ident(t)) if kind == 'id' else 1
            b = float(sum(pieces_bits[k:k + n]))
            if kind == 'id':  # coined words also pay their spelling
                for j, p in zip(range(k, k + n), split_ident(t)):
                    if unk_flags[j]:
                        if p in seen:
                            b += 1 + math.log2(len(seen))
                        else:
                            b += 1 + voc.spell_bits(p)
                            seen[p] = True
            if kind == 'num' and sum(c.isdigit() for c in t) >= LONGNUM_DIGITS:
                b += literal_bits(t)
            spans.append([t, round(b, 2)])
            k += n
            pos = mt.end()
        spans.append([src[pos:], None])
        if src is d['statement'] and d['proof']:
            spans.append([':=', None])
    kw = d['text'][: d['text'].find(d['statement'])] if d['statement'] in d['text'] else ''
    shown = sum(b for _, b in spans if b is not None) + float(bits[-1])
    out.append(dict(label=label, corpus=r.corpus, project=r.project, name=r.full, kind=r.kind,
                    prefix=kw, bits_per_tok=shown / int(r.n_tok), tokens=int(r.n_tok), bits=shown,
                    spans=spans))
json.dump(out, open('data/out/heat.json', 'w'), ensure_ascii=False, indent=0)
for x in out:
    print(x['label'], x['project'], x['name'], round(x['bits_per_tok'], 2), x['tokens'])
