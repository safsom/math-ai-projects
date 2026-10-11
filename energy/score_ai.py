"""Text energy of the other AI corpora under the 5-gram KN model of all of mathlib (as score_text.py
scores every non-mathlib corpus). Output: data/text_energy_ai.pkl and data/out/projects_ai.csv
(per-project e_tok = bits per token, long numerals excluded, as in analysis.py).
"""
import gc, pickle, sys
import pandas as pd
from kn import KN, Encoded, Vocab, decl_energies

ORDER = 5
META = ['corpus', 'project', 'file', 'kind', 'full', 'cert']


def score(model, voc, decls, chunk=20000):  # as in score_text.py
    rows = []
    decls = sorted(decls, key=lambda d: d['project'])
    coined = {}
    for i in range(0, len(decls), chunk):
        part = decls[i:i + chunk]
        r = decl_energies(model, Encoded(part, voc, ORDER, coined))
        df = pd.DataFrame({k: v for k, v in r.items()})
        for k in META:
            df[k] = [d.get(k) for d in part]
        rows.append(df)
    return pd.concat(rows, ignore_index=True)

NEW = sys.argv[1:] or ['ai_flt', 'ai_spherepacking', 'ai_erdos90', 'ai_putnam2025', 'ai_imo2025']
m = pickle.load(open('data/decls_mathlib.pkl', 'rb'))['decls']
voc = Vocab(m)
M = KN(Encoded(m, voc, ORDER), ORDER)
del m
gc.collect()
out = []
for c in NEW:
    d = pickle.load(open(f'data/decls_{c}.pkl', 'rb'))['decls']
    out.append(score(M, voc, d))
    print(c, len(d), flush=True)
df = pd.concat(out, ignore_index=True)
df.to_pickle('data/text_energy_ai.pkl')
proj = df.groupby(['corpus', 'project']).apply(
    lambda g: pd.Series({'n_sampled': len(g), 'e_tok': g.E_struct.sum() / g.n_tok.sum()})).reset_index()
proj.to_csv('data/out/projects_ai.csv', index=False)
print(proj.groupby('corpus').e_tok.describe())
