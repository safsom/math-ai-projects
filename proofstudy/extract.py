"""Two-pass extraction over all corpora.

pass 1: parse every file -> chunked pickles of declarations + the global table of
        declared names (including generated names: structure fields, ctors,
        to_additive translations).
pass 2: resolve every identifier of every declaration against the table, compute
        per-declaration features, write features + dependency edges.

Usage: python3 extract.py OUTDIR
"""
from __future__ import annotations

import gzip
import os
import pickle
import re
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from leanparse import (IDENT_RE, NUM_RE, TOKEN_RE, TACTICS, _COMP, _conclusion, norm_hash,  # noqa: E402
                       parse_file, skeleton_hash)

# ---- local binders (Lean resolves locals before globals) -------------------
# Only genuine binding sites are used: the signature's binder section, binder
# lists after fun/∀/∃/big operators, and the binder slots of tactics. Type
# ascriptions such as `(le_trans h₁ h₂ : a ≤ c)` are NOT binders.
_ID = rf"{_COMP}"
_BINDER_GROUP = re.compile(rf"[(\{{\[⦃]\s*((?:{_ID}\s+)*{_ID})\s*:(?!=)")
_QUANT_START = re.compile(r"(?:∀|∃!?|\bfun\b|λ|∑'?|∏'?|⋃|⋂|⨆|⨅|∫⁻?|∮|⨁|\bΠ|\bΣ)")
_STOP = ":"
_TAC_BIND = re.compile(rf"\b(?:intro|intros|rintro|ext|funext|by_contra!?|by_cases|have|haveI|let|set|obtain|"
                       rf"rename_i|next|case)\b([^\n]*?)(?=:=|:|\busing\b|\bwith\b|\bat\b|$)", re.M)
_WITH = re.compile(r"\bwith\b([^\n]*?)(?=:=|\busing\b|$)", re.M)
_CHOOSE = re.compile(r"\bchoose!?\b([^\n]*?)\busing\b")
_GENERALIZE = re.compile(rf"\bgeneralize\b[^\n]*?=\s*({_ID})")
_CASE_ARM = re.compile(rf"^\s*\|\s*{_ID}((?:\s+{_ID})*)\s*=>", re.M)
_OPEN, _CLOSE = "({[⦃⟨", ")}]⦄⟩"


def _scan_binders(text, i, n_max=400):
    """Binders following a quantifier at text[i:]: idents and bracketed groups,
    until ',' '=>' '↦' ':' '∈' or anything else."""
    out = []
    n = min(len(text), i + n_max)
    while i < n:
        while i < n and text[i] in " \t\n":
            i += 1
        if i >= n:
            break
        c = text[i]
        if c in _OPEN:
            depth, j = 0, i
            while j < n:
                if text[j] in _OPEN:
                    depth += 1
                elif text[j] in _CLOSE:
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            grp = text[i + 1:j]
            if c == "⟨":
                out += IDENT_RE.findall(grp)
            else:
                k = grp.find(":")
                if k > 0:
                    out += IDENT_RE.findall(grp[:k])
            i = j + 1
            continue
        m = IDENT_RE.match(text, i)
        if m and m.group() not in ("in",):
            out.append(m.group())
            i = m.end()
            continue
        if c == "_":
            i += 1
            continue
        break
    return out


def local_names(sig, body, binder_part=None):
    loc = set()
    if binder_part is None:
        binder_part = sig[: len(sig) - len(_conclusion(sig))]
    for m in _BINDER_GROUP.finditer(binder_part):
        loc.update(IDENT_RE.findall(m.group(1)))
    for text in (sig, body):
        for m in _QUANT_START.finditer(text):
            loc.update(_scan_binders(text, m.end()))
    for rx in (_TAC_BIND, _WITH, _CHOOSE, _GENERALIZE, _CASE_ARM):
        for m in rx.finditer(body):
            loc.update(IDENT_RE.findall(m.group(1)))
    return {x for x in loc if "." not in x}

OAI = Path("/tmp/oai-math/lean")
C = Path("/tmp/corpora")

# corpus name -> (root dir to walk, role, project-key function)
def _proj_depth2(base):
    def f(rel):
        p = Path(rel).relative_to(base).parts
        return "/".join(p[:2]) if len(p) > 2 else (p[0] if len(p) > 1 else "_root")
    return f


def _proj_depth1(base, prefix):
    def f(rel):
        p = Path(rel).relative_to(base).parts
        return f"{prefix}/" + (p[0] if len(p) > 1 else "_root")
    return f


CORPORA = {
    # role: 'subject' (analysed), 'control' (analysed), 'base' (resolution only)
    "core":      dict(root=C / "lean4/src", role="base", project=lambda r: "core"),
    "batteries": dict(root=C / "batteries/Batteries", role="base", project=lambda r: "batteries"),
    "mathlib":   dict(root=C / "mathlib/Mathlib", role="control", group="mathlib",
                      project=_proj_depth2(C / "mathlib/Mathlib")),
    "oai":       dict(root=OAI / "OAI", role="subject", group="openai_math",
                      project=_proj_depth2(OAI / "OAI")),
    "tenproofs": dict(root=Path("/tmp/ten-proofs"), role="subject", group="openai_ten",
                      project=lambda r: Path(r).stem, exclude=("ComparatorChallenges", "All.lean", ".lake")),
    "carleson":  dict(root=C / "carleson/Carleson", role="control", group="human_research",
                      project=_proj_depth1(C / "carleson/Carleson", "carleson")),
    "sphere":    dict(root=C / "sphere-eversion/SphereEversion", role="control", group="human_research",
                      project=_proj_depth1(C / "sphere-eversion/SphereEversion", "sphere")),
    "pfr":       dict(root=C / "pfr/PFR", role="control", group="human_research",
                      project=_proj_depth1(C / "pfr/PFR", "pfr")),
    "flt":       dict(root=C / "flt/FLT", role="control", group="human_research",
                      project=_proj_depth1(C / "flt/FLT", "flt")),
    "strongpnt": dict(root=C / "strongpnt/StrongPNT", role="control", group="other_ai",
                      project=lambda r: "strongpnt/" + Path(r).stem),
}
# what each corpus may resolve against, besides itself (order = priority)
BASE = ["core", "batteries", "mathlib"]
EXTRA_DEPS = {"oai": ["carleson", "sphere", "strongpnt"]}

KEYWORDS = {"fun", "by", "have", "show", "from", "let", "in", "if", "then", "else", "match", "with",
            "do", "at", "only", "using", "Type", "Sort", "Prop", "sorry", "this", "calc", "where",
            "forall", "exists", "λ", "true", "false", "return", "for", "end", "suffices", "obtain",
            "intro", "exact", "apply", "simp", "rw", "decide"}


def corpus_files(name):
    cfg = CORPORA[name]
    excl = cfg.get("exclude", ())
    out = []
    for p in sorted(Path(cfg["root"]).rglob("*.lean")):
        rel = str(p)
        if any(e in p.parts or p.name == e for e in excl):
            continue
        if ".lake" in p.parts:
            continue
        out.append(rel)
    return out


# ----------------------------------------------------------------- pass 1 ---
def _p1_chunk(args):
    corpus, idx, files, outdir = args
    proj = CORPORA[corpus]["project"]
    decls, names = [], []
    fails = 0
    for f in files:
        try:
            src = open(f, encoding="utf-8", errors="replace").read()
            ds = parse_file(src, f)
        except Exception:
            fails += 1
            continue
        pj = proj(f)
        for d in ds:
            d["project"] = pj
            if d["name"]:
                names.append(d["name"])
            names.extend(d.get("generated", ()))
            decls.append(d)
    with gzip.open(f"{outdir}/p1_{corpus}_{idx:05d}.pkl.gz", "wb", compresslevel=3) as fh:
        pickle.dump(decls, fh, protocol=5)
    return corpus, names, len(decls), fails


def pass1(outdir, chunk=1500):
    jobs = []
    for corpus in CORPORA:
        fs = corpus_files(corpus)
        for i in range(0, len(fs), chunk):
            jobs.append((corpus, i // chunk, fs[i:i + chunk], outdir))
    tables = {c: set() for c in CORPORA}
    counts = Counter()
    with Pool(2) as pool:
        for corpus, names, n, fails in pool.imap_unordered(_p1_chunk, jobs):
            tables[corpus].update(names)
            counts[corpus] += n
            counts[corpus + "_fail"] += fails
    with open(f"{outdir}/tables.pkl", "wb") as fh:
        pickle.dump(tables, fh, protocol=5)
    return tables, counts


# ----------------------------------------------------------------- pass 2 ---
_TABLES = None
_ORDER = None


_LAST = {}
_BASE_LAST = None


def _init2(outdir):
    global _TABLES, _BASE_LAST
    with open(f"{outdir}/tables.pkl", "rb") as fh:
        _TABLES = pickle.load(fh)
    _BASE_LAST = {n.rsplit(".", 1)[-1] for b in BASE for n in _TABLES[b]}


def _own_last(corpus):
    """last component -> unique full name in this corpus (None if ambiguous).
    Used to resolve generalised field notation `h.foo` when `foo` is unique in
    the corpus and is not also a last component anywhere in core/batteries/mathlib."""
    m = _LAST.get(corpus)
    if m is None:
        m = {}
        for n in _TABLES[corpus]:
            k = n.rsplit(".", 1)[-1]
            m[k] = None if k in m else n
        _LAST[corpus] = m
    return m


def _resolver(corpus):
    order = [corpus] + EXTRA_DEPS.get(corpus, []) + [b for b in BASE if b != corpus]
    tabs = [(c, _TABLES[c]) for c in order]
    extra = set(EXTRA_DEPS.get(corpus, []))
    cache = {}

    def resolve(ident, ns, opens):
        key = (ident, ns, opens)
        r = cache.get(key)
        if r is not None:
            return r
        comps = ident.split(".")
        chain = []
        if comps[0] == "_root_":
            comps = comps[1:]
            chain = [""]
        else:
            parts = ns.split(".") if ns else []
            chain = [".".join(parts[:k]) for k in range(len(parts), -1, -1)]
        res = (None, None, False)
        for k in range(len(comps), 0, -1):
            p = ".".join(comps[:k])
            cands = [(pre + "." + p) if pre else p for pre in chain]
            for o in opens:
                for pre in chain:
                    cands.append(((pre + ".") if pre else "") + o + "." + p)
            hit = None
            for c in cands:
                root = "." not in c
                for cn, t in tabs:
                    if c in t:
                        if root and (len(c) <= 2 or cn in extra):
                            continue
                        hit = (c, cn)
                        break
                if hit:
                    break
            if hit:
                res = (hit[0], hit[1], k == len(comps))
                break
        cache[key] = res
        return res

    return resolve


def _tokens(s):
    return TOKEN_RE.findall(s)


def _features(d, resolve, corpus):
    sig, body = d["sig"], d["body"]
    ns = d["ns"]
    opens = tuple(dict.fromkeys(d["opens"]))
    sig_ids = IDENT_RE.findall(sig)
    body_ids = IDENT_RE.findall(body)
    loc = local_names(sig, body)
    _res = resolve

    def resolve(tok, ns, opens):  # noqa: F811  (shadow-aware wrapper)
        if tok in loc:
            return (None, None, False)
        return _res(tok, ns, opens)
    sig_refs, body_refs = {}, {}
    unresolved_q = 0
    prefix_only = 0
    sig_norm = []
    local_map = {}
    for tok in _tokens(sig):
        if IDENT_RE.fullmatch(tok) and tok not in KEYWORDS:
            full, cn, exact = resolve(tok, ns, opens)
            if full:
                sig_refs[full] = cn
                sig_norm.append(full if exact else full + ".?")
            else:
                head = tok.split(".")[0]
                sig_norm.append(local_map.setdefault(head, f"v{len(local_map)}") + tok[len(head):])
        else:
            sig_norm.append(tok)
    dot_resolved = 0
    own_last = _own_last(corpus)
    for tok in set(body_ids) | {t for t in sig_ids if "." in t}:
        if tok in KEYWORDS or tok in TACTICS:
            continue
        full, cn, exact = resolve(tok, ns, opens)
        if full and exact:
            body_refs.setdefault(full, cn)
            continue
        if "." in tok:
            # generalised field notation: x.foo / x.foo.bar  -> unique own-corpus foo
            head, rest = tok.split(".", 1)
            if not full or head in loc:
                k = rest.split(".")[0]
                tgt = own_last.get(k)
                if tgt and k not in _BASE_LAST:
                    body_refs.setdefault(tgt, corpus)
                    dot_resolved += 1
                    continue
        if full:
            body_refs.setdefault(full, cn)
            prefix_only += 1
        elif "." in tok and tok[:1].isupper():
            unresolved_q += 1
    btoks = _tokens(body)
    stoks = _tokens(sig)
    tac = Counter()
    for t in btoks:
        cat = TACTICS.get(t)
        if cat:
            tac[cat] += 1
            tac[t] += 1
    nums = NUM_RE.findall(body)
    big = sum(1 for x in nums if len(x.replace(".", "")) >= 3)
    hints = [len(h.split(",")) for h in re.findall(r"nlinarith\s*\[([^\]]*)\]", body)]
    concl = _conclusion(sig)
    feats = dict(
        path=d["path"], line=d["line"], kind=d["kind"], name=d["name"], private=d["private"],
        project=d["project"], ns=ns,
        attr_simp=any(a.startswith("simp") or ", simp" in a for a in d["attrs"]),
        attr_to_additive=any("to_additive" in a for a in d["attrs"]),
        n_sig_tok=len(stoks), n_body_tok=len(btoks), n_concl_tok=len(_tokens(concl)),
        n_body_lines=body.count("\n") + (1 if body else 0),
        n_num=len(nums), n_bignum=big,
        t_enum=tac["enum"], t_auto=tac["auto"], t_struct=tac["struct"],
        t_decide=tac["decide"] + tac["native_decide"], t_fin_cases=tac["fin_cases"],
        t_interval_cases=tac["interval_cases"], t_nlinarith=tac["nlinarith"], t_simp=tac["simp"] + tac["simp_all"] + tac["simpa"],
        t_omega=tac["omega"], t_norm_num=tac["norm_num"], t_linarith=tac["linarith"],
        t_allgoals=body.count("<;>") + body.count("all_goals"),
        nlinarith_hint_max=max(hints) if hints else 0,
        is_term_proof=not body.lstrip().startswith("by") and d["kind"] in ("theorem", "lemma"),
        n_unresolved_q=unresolved_q, n_prefix_only=prefix_only, n_dot_resolved=dot_resolved,
        body_hash=norm_hash(body) if body else "", skel_hash=skeleton_hash(body) if body else "",
        sig_hash=norm_hash(" ".join(sig_norm)) if sig and d["kind"] in ("theorem", "lemma") else "",
        sig_text=" ".join(sig.split())[:600],
    )
    return feats, sig_refs, body_refs


def _p2_chunk(args):
    path, outdir = args
    corpus = Path(path).name.split("_")[1]
    resolve = _resolver(corpus)
    with gzip.open(path, "rb") as fh:
        decls = pickle.load(fh)
    rows, edges = [], []
    for d in decls:
        f, sr, br = _features(d, resolve, corpus)
        f["corpus"] = corpus
        rows.append(f)
        edges.append((list(sr.items()), [(k, v) for k, v in br.items() if k not in sr]))
    out = Path(outdir) / Path(path).name.replace("p1_", "p2_")
    with gzip.open(out, "wb", compresslevel=3) as fh:
        pickle.dump((rows, edges), fh, protocol=5)
    return corpus, len(rows)


def pass2(outdir):
    chunks = sorted(str(p) for p in Path(outdir).glob("p1_*.pkl.gz")
                    if CORPORA[p.name.split("_")[1]]["role"] != "base")
    done = Counter()
    with Pool(2, initializer=_init2, initargs=(outdir,)) as pool:
        for corpus, n in pool.imap_unordered(_p2_chunk, [(c, outdir) for c in chunks]):
            done[corpus] += n
    return done


if __name__ == "__main__":
    outdir = sys.argv[1]
    os.makedirs(outdir, exist_ok=True)
    stage = sys.argv[2] if len(sys.argv) > 2 else "all"
    if stage in ("all", "1"):
        tables, counts = pass1(outdir)
        print("pass1", dict(counts), {k: len(v) for k, v in tables.items()}, flush=True)
    if stage in ("all", "2"):
        print("pass2", dict(pass2(outdir)), flush=True)
