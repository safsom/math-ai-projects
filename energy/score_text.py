"""Text energy of every sampled declaration under a 5-gram KN model of mathlib.

mathlib declarations are scored by the fold model that never saw their project (5-fold project split);
every other corpus is scored by the model trained on all of mathlib. Output: data/text_energy.pkl
"""
import gc, pickle, random, numpy as np, pandas as pd
from kn import KN, Encoded, Vocab, decl_energies

ORDER = 5
CORPORA = ['mathlib', 'openai', 'tenproofs', 'carleson', 'flt', 'pfr', 'sphere', 'strongpnt']
META = ['corpus', 'project', 'file', 'kind', 'full', 'cert']


def score(model, voc, decls, chunk=20000):
    rows = []
    decls = sorted(decls, key=lambda d: d['project'])  # stable: keeps sample order within a project
    coined = {}
    for i in range(0, len(decls), chunk):
        part = decls[i:i + chunk]
        r = decl_energies(model, Encoded(part, voc, ORDER, coined))
        df = pd.DataFrame({k: v for k, v in r.items()})
        for k in META:
            df[k] = [d.get(k) for d in part]
        rows.append(df)
    return pd.concat(rows, ignore_index=True)


data = {c: pickle.load(open(f'data/decls_{c}.pkl', 'rb'))['decls'] for c in CORPORA}
m = data['mathlib']
projs = sorted({d['project'] for d in m})
rng = random.Random(7); rng.shuffle(projs)
fold = {p: i % 5 for i, p in enumerate(projs)}
out = []
for f in range(5):
    tr = [d for d in m if fold[d['project']] != f]
    te = [d for d in m if fold[d['project']] == f]
    voc = Vocab(tr)
    M = KN(Encoded(tr, voc, ORDER), ORDER)
    out.append(score(M, voc, te))
    print('fold', f, len(te), flush=True)
    del M; gc.collect()
voc = Vocab(m)
M = KN(Encoded(m, voc, ORDER), ORDER)
for c in CORPORA[1:]:
    out.append(score(M, voc, data[c]))
    print(c, len(data[c]), flush=True)
df = pd.concat(out, ignore_index=True)
df.to_pickle('data/text_energy.pkl')
print(df.groupby('corpus').apply(lambda g: pd.Series({'decls': len(g), 'bits_per_tok': g.E_struct.sum() / g.n_tok.sum()})))
