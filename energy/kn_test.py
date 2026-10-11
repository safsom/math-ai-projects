import pickle, numpy as np, time, random
from kn import *
m = pickle.load(open('data/decls_mathlib.pkl','rb'))
print('mathlib decls', len(m['decls']), 'projects', len(m['projects']))
projs = sorted({d['project'] for d in m['decls']})
random.seed(0); test = set(random.sample(projs, 20))
tr = [d for d in m['decls'] if d['project'] not in test][:60000]
te = [d for d in m['decls'] if d['project'] in test][:5000]
t=time.time(); voc = Vocab(tr); enc = Encoded(tr, voc, 4); print('enc', time.time()-t, len(enc.toks), voc.size)
t=time.time(); M = KN(enc, 4); print('train', time.time()-t)
# normalization: for a few 3-token contexts, sum q(w|ctx) over the vocabulary
class S: pass
for ctx in [enc.toks[10:13], enc.toks[500:503], np.array([PAD,PAD,PAD]), np.array([5,77,1234])]:
    s = S(); W = np.arange(voc.size)
    s.toks = np.stack([np.tile(ctx,(len(W),1)).T, W[None,:]],0) if False else None
    st = np.concatenate([np.concatenate([[PAD], ctx, [w]]) for w in W])
    s.toks = st
    idx, bits = M.logprob2(s)
    last = idx[(idx % 5) == 4]
    p = 2.0 ** -bits[np.isin(idx, last)]
    print('sum q(w|ctx) =', p.sum())
for name, ds in [('train-sample', tr[:5000]), ('heldout', te), ('pfr', pickle.load(open('data/decls_pfr.pkl','rb'))['decls']), ('strongpnt', pickle.load(open('data/decls_strongpnt.pkl','rb'))['decls'])]:
    e = Encoded(ds, voc, 4); r = decl_energies(M, e)
    print(name, 'bits/tok %.3f'%(r['E_struct'].sum()/r['n_tok'].sum()), 'unk-rate %.4f'%(r['n_unk'].sum()/r['n_tok'].sum()), 'lit/tok %.3f'%(r['E_lit'].sum()/r['n_tok'].sum()))
