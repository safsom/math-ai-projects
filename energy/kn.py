"""Interpolated Kneser-Ney n-gram model over Lean tokens, vectorized with 64-bit n-gram hashes.

Energy of a token sequence x under the model q is E(x) = -log2 q(x) bits. Out-of-vocabulary pieces
are coded as <unk> followed by a character-level spelling (unigram characters with a stop symbol),
so E is a proper code length.
"""
import math
from collections import Counter

import numpy as np

from lexer import lm_tokens

PAD, EOS, UNK = 0, 1, 2
MULT = np.uint64(0x9E3779B97F4A7C15)
CLS_CODE = {"n": 0, "k": 1, "o": 2, "e": 3}  # name piece, numeral, operator, end-of-declaration


def decl_tokens(d):
    st, cs, lit1 = lm_tokens(d["statement"])
    pt, pc, lit2 = lm_tokens(d["proof"])
    return st, cs, pt, pc, lit1 + lit2


class Encoded:
    """A batch of declarations flattened into one padded token stream."""

    def __init__(self, decls, vocab, order, coined=None):
        # coined: project -> {piece: True} of out-of-vocabulary pieces already spelled in that project.
        # A coined piece is spelled once (1 flag bit + spelling); later uses cost 1 flag bit + log2(#coined).
        coined = {} if coined is None else coined
        toks, cls, part, owner, lits, unkbits = [], [], [], [], [], []
        self.n = len(decls)
        for i, d in enumerate(decls):
            st, cs, pt, pc, lit = decl_tokens(d)
            seq = st + pt
            toks.extend([PAD] * (order - 1))
            cls.extend([-1] * (order - 1))
            part.extend([0] * (order - 1))
            owner.extend([-1] * (order - 1))
            ub = 0.0
            seen = coined.setdefault(d.get('project'), {})
            for t in seq:
                j = vocab.ids.get(t)
                if j is None:
                    toks.append(UNK)
                    if t in seen:
                        ub += 1 + math.log2(len(seen))
                    else:
                        ub += 1 + vocab.spell_bits(t)
                        seen[t] = True
                else:
                    toks.append(j)
            toks.append(EOS)
            cls.extend(CLS_CODE[c] for c in cs + pc)
            cls.append(CLS_CODE["e"])
            part.extend([0] * len(st) + [1] * len(pt) + [1])
            owner.extend([i] * (len(seq) + 1))
            lits.append(lit)
            unkbits.append(ub)
        self.toks = np.asarray(toks, dtype=np.int64)
        self.cls = np.asarray(cls, dtype=np.int8)
        self.part = np.asarray(part, dtype=np.int8)
        self.owner = np.asarray(owner, dtype=np.int64)
        self.lit = np.asarray(lits)
        self.unkbits = np.asarray(unkbits)


class Vocab:
    def __init__(self, decls, min_count=2):
        c = Counter()
        chars = Counter()
        for d in decls:
            st, _, pt, _, _ = decl_tokens(d)
            c.update(st)
            c.update(pt)
        self.ids = {}
        for t, n in c.items():
            if n >= min_count:
                self.ids[t] = len(self.ids) + 3
            for ch in t:
                chars[ch] += n
        tot = sum(chars.values()) + len(c)  # stop symbol once per word occurrence type, smoothed below
        stop = len(c) / tot
        self.size = len(self.ids) + 3
        self._lp = {ch: -math.log2((n + 0.5) / (tot + 0.5 * 65536)) for ch, n in chars.items()}
        self._lp_unseen = -math.log2(0.5 / (tot + 0.5 * 65536))
        self._stop = -math.log2(stop)

    def spell_bits(self, t):
        return sum(self._lp.get(ch, self._lp_unseen) for ch in t) + self._stop


def ngram_hashes(toks, order):
    """H[k][i] = hash of toks[i-k+1 .. i] for k = 1..order (positions i < k-1 are garbage)."""
    t = toks.astype(np.uint64) + np.uint64(1)
    H = [None, t * MULT]
    with np.errstate(over="ignore"):
        for k in range(2, order + 1):
            prev = np.empty_like(t)
            prev[0] = 0
            prev[1:] = H[k - 1][:-1]
            H.append((prev ^ np.uint64(k)) * MULT + t * np.uint64(0xC2B2AE3D27D4EB4F))
    return H


def _discount(cnt):
    n1 = np.count_nonzero(cnt == 1)
    n2 = np.count_nonzero(cnt == 2)
    return n1 / (n1 + 2 * n2) if n1 + 2 * n2 else 0.5


class KN:
    def __init__(self, enc: Encoded, order=4):
        self.order = order
        toks = enc.toks
        pred = toks != PAD
        H = ngram_hashes(toks, order)
        self.V = int(toks.max()) + 1
        self.tables = [None] * (order + 1)
        # Highest order uses raw counts; lower orders use continuation counts (distinct left contexts).
        left_ext = None
        for k in range(order, 0, -1):
            hk = H[k][pred]
            uniq, first, cnt = np.unique(hk, return_index=True, return_counts=True)
            if k < order:
                # continuation count of a k-gram = number of distinct (k+1)-grams ending in it
                sk, ck = np.unique(left_ext, return_counts=True)
                pos = np.searchsorted(sk, uniq)
                pos = np.minimum(pos, len(sk) - 1)
                cnt = np.where(sk[pos] == uniq, ck[pos], 1)
            idx = np.flatnonzero(pred)[first]
            # suffix (k-1)-gram of each unique k-gram -> left extension list for order k-1
            left_ext = H[k - 1][idx] if k > 1 else None
            if k > 1:
                ctx = H[k - 1][idx - 1]
                order_c = np.argsort(ctx, kind="stable")
                cs, cstart = np.unique(ctx[order_c], return_index=True)
                csum = np.add.reduceat(cnt[order_c], cstart)
                ctypes = np.diff(np.append(cstart, len(order_c)))
            else:
                cs = csum = ctypes = None
            self.tables[k] = dict(keys=uniq, cnt=cnt.astype(np.float64), D=_discount(cnt),
                                  ckeys=cs, csum=None if csum is None else csum.astype(np.float64),
                                  ctypes=ctypes)
        t1 = self.tables[1]
        t1["S"] = t1["cnt"].sum()
        t1["T"] = len(t1["keys"])

    @staticmethod
    def _lookup(keys, vals, q, default):
        pos = np.searchsorted(keys, q)
        pos = np.minimum(pos, len(keys) - 1)
        hit = keys[pos] == q
        return np.where(hit, vals[pos], default), hit

    def logprob2(self, enc: Encoded):
        """-log2 q(token | context) for every predicted position of the stream."""
        toks = enc.toks
        H = ngram_hashes(toks, self.order)
        pred = toks != PAD
        idx = np.flatnonzero(pred)
        t1 = self.tables[1]
        c1, _ = self._lookup(t1["keys"], t1["cnt"], H[1][idx], 0.0)
        D = t1["D"]
        p = (np.maximum(c1 - D, 0) + D * t1["T"] / self.V) / t1["S"]
        for k in range(2, self.order + 1):
            tk = self.tables[k]
            ck, _ = self._lookup(tk["keys"], tk["cnt"], H[k][idx], 0.0)
            ctx = H[k - 1][idx - 1]
            s, hit = self._lookup(tk["ckeys"], tk["csum"], ctx, 1.0)
            ty, _ = self._lookup(tk["ckeys"], tk["ctypes"].astype(np.float64), ctx, 0.0)
            D = tk["D"]
            pk = (np.maximum(ck - D, 0) + D * ty * p) / s
            p = np.where(hit, pk, p)
        return idx, -np.log2(p)


def decl_energies(model: KN, enc: Encoded):
    """Per-declaration energy totals, split by token class and statement/proof."""
    idx, bits = model.logprob2(enc)
    own = enc.owner[idx]
    cls = enc.cls[idx]
    part = enc.part[idx]
    n = enc.n
    out = {
        "E_tok": np.bincount(own, weights=bits, minlength=n),
        "n_tok": np.bincount(own, minlength=n).astype(float),
        "E_proof": np.bincount(own, weights=bits * (part == 1), minlength=n),
        "n_proof": np.bincount(own, weights=(part == 1).astype(float), minlength=n),
        "E_unk": enc.unkbits,
        "E_lit": enc.lit,
        "n_unk": np.bincount(own, weights=(enc.toks[idx] == UNK).astype(float), minlength=n),
    }
    for name, code in CLS_CODE.items():
        m = cls == code
        out[f"E_{name}"] = np.bincount(own, weights=bits * m, minlength=n)
        out[f"n_{name}"] = np.bincount(own, weights=m.astype(float), minlength=n)
    out["E_total"] = out["E_tok"] + out["E_unk"] + out["E_lit"]
    out["E_struct"] = out["E_tok"] + out["E_unk"]  # everything except long-numeral digits
    return out
