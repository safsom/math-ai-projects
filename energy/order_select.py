"""Pick the n-gram order by held-out mathlib cross-entropy (one fold of a 5-fold project split)."""
import pickle, random, time, numpy as np
from kn import *
m = pickle.load(open('data/decls_mathlib.pkl','rb'))
projs = sorted({d['project'] for d in m['decls']})
rng = random.Random(7); rng.shuffle(projs)
fold = {p: i % 5 for i, p in enumerate(projs)}
tr = [d for d in m['decls'] if fold[d['project']] != 0]
te = [d for d in m['decls'] if fold[d['project']] == 0]
voc = Vocab(tr)
for order in [3, 4, 5, 6]:
    t = time.time()
    M = KN(Encoded(tr, voc, order), order)
    r = decl_energies(M, Encoded(te, voc, order))
    print(order, 'heldout bits/tok %.4f' % (r['E_struct'].sum() / r['n_tok'].sum()), 'time %.0fs' % (time.time() - t), flush=True)
    del M
