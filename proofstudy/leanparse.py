"""Syntactic Lean 4 source parser for corpus-scale proof-style measurement.

No elaboration: this reads source text, tracks namespaces / sections / opens,
splits files into top-level commands, and extracts each declaration's name,
kind, signature, body, identifiers and tactic usage. Name resolution against a
global table happens in a separate pass (resolve.py).

Design choices (all deliberate, all reported as limitations):
  * Top-level commands are recognised by a non-blank character in column 0,
    which is how mathlib-style Lean is laid out. Lines in column 0 that start
    with continuation tokens (| ) ] } := where deriving ...) are glued back on.
  * Comments and string literals are removed before anything else.
  * Generalised field notation (h.le, s.card) cannot be resolved without types;
    such references are not counted, so dependency counts are lower bounds.
"""
from __future__ import annotations

import re
import hashlib

# ---------------------------------------------------------------- lexing ----
_LETTER = ("A-Za-z_À-ɏ"
           "Α-ΟΡΤ-Ω"      # Greek capitals except Π Σ
           "α-κμ-ω"             # Greek lower except λ
           "ἀ-῾℀-⅏"
           "\U0001d49c-\U0001d59f")
_CONT = _LETTER + "0-9'!?₀-₌ₐ-ₜᵢ-ᵪ"
_COMP = rf"(?:«[^»\n]*»|[{_LETTER}][{_CONT}]*)"
IDENT_RE = re.compile(rf"(?<![{_CONT}.]){_COMP}(?:\.{_COMP})*")
NUM_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])")
TOKEN_RE = re.compile(rf"{_COMP}(?:\.{_COMP})*|\d+(?:\.\d+)?|:=|=>|<;>|->|→|↔|[^\s]")

_SPECIAL = re.compile(r'--|/-|"')
_BLOCK = re.compile(r"/-|-/")


def strip_comments(src: str) -> str:
    """Remove line comments, nested block comments (incl. doc comments) and the
    contents of string literals. Newlines inside removed blocks are kept so that
    line structure (and column-0 detection) survives."""
    out = []
    i, n = 0, len(src)
    while i < n:
        m = _SPECIAL.search(src, i)
        if not m:
            out.append(src[i:])
            break
        j = m.start()
        tok = m.group()
        # char literal '"' must not open a string
        if tok == '"' and j > 0 and src[j - 1] == "'" and j + 1 < n and src[j + 1] == "'":
            out.append(src[i:j + 2])
            i = j + 2
            continue
        out.append(src[i:j])
        if tok == "--":
            k = src.find("\n", j)
            i = n if k < 0 else k
        elif tok == "/-":
            depth, k = 1, j + 2
            while depth and k < n:
                mm = _BLOCK.search(src, k)
                if not mm:
                    k = n
                    break
                depth += 1 if mm.group() == "/-" else -1
                k = mm.end()
            out.append("\n" * src.count("\n", j, k))
            i = k
        else:  # string literal
            k = j + 1
            while k < n:
                c = src[k]
                if c == "\\":
                    k += 2
                    continue
                if c == '"':
                    k += 1
                    break
                k += 1
            out.append('""')
            out.append("\n" * src.count("\n", j, k))
            i = k
    return "".join(out)


# ------------------------------------------------------ command splitting ---
_CONTINUATION = re.compile(r"^(\||\)|\]|\}|⟩|:=|where\b|deriving\b|with\b|termination_by\b|decreasing_by\b|·|<;>|then\b|else\b|fun\b|by\b)")


_INDENTED_DECL = re.compile(r"^\s+(?:@\[[^\n]*?\]\s*)*(?:(?:private|protected|noncomputable|nonrec|partial|unsafe|public|meta)\s+)*"
                            r"(?:theorem|lemma|def|abbrev|instance|structure|class|inductive|opaque|axiom|example|irreducible_def)\s")


def split_commands(text: str):
    """Yield (start_line, command_text) for each top-level command."""
    lines = text.split("\n")
    cur, start = [], 0
    for idx, line in enumerate(lines):
        if (line and not line[0].isspace() and not _CONTINUATION.match(line)) or \
                (line[:1].isspace() and _INDENTED_DECL.match(line)):
            if cur and any(l.strip() for l in cur):
                yield start, "\n".join(cur)
            cur, start = [line], idx + 1
        else:
            cur.append(line)
    if cur and any(l.strip() for l in cur):
        yield start, "\n".join(cur)


# --------------------------------------------------------- declarations -----
DECL_KINDS = {"theorem", "lemma", "def", "abbrev", "instance", "structure", "class",
              "inductive", "opaque", "axiom", "example", "irreducible_def", "alias",
              "coinductive"}
MODIFIERS = {"private", "protected", "noncomputable", "nonrec", "partial", "unsafe",
             "scoped", "local", "public", "meta"}
_WORD = re.compile(r"\S+")


def _consume_attrs(s: str, i: int):
    """Consume @[...] blocks (balanced brackets) starting at i. Returns (attrs, i)."""
    attrs = []
    n = len(s)
    while True:
        while i < n and s[i].isspace():
            i += 1
        if s.startswith("@[", i):
            depth, k = 0, i + 1
            while k < n:
                if s[k] == "[":
                    depth += 1
                elif s[k] == "]":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            attrs.append(s[i + 2:k])
            i = k + 1
        else:
            return attrs, i


def _split_top(s: str):
    """Find the signature/body boundary at bracket depth 0: first ':=', 'where',
    or a line starting with '|'. Returns (sig, body, sep)."""
    depth = 0
    i, n = 0, len(s)
    opens, closes = "([{⟨⦃", ")]}⟩⦄"
    while i < n:
        c = s[i]
        if c in opens:
            depth += 1
        elif c in closes:
            depth = max(0, depth - 1)
        elif depth == 0:
            if c == ":" and i + 1 < n and s[i + 1] == "=":
                return s[:i], s[i + 2:], ":="
            if c == "w" and s.startswith("where", i) and (i == 0 or not s[i - 1].isalnum() and s[i - 1] not in "_.'") \
                    and (i + 5 >= n or not (s[i + 5].isalnum() or s[i + 5] in "_'")):
                return s[:i], s[i + 5:], "where"
            if c == "|" and (i == 0 or s[i - 1] == "\n" or s[:i].rstrip(" ").endswith("\n")):
                return s[:i], s[i:], "|"
        i += 1
    return s, "", ""


def _conclusion(sig: str) -> str:
    """Text after the last ':' at depth 0 (the statement's conclusion/type)."""
    depth, last = 0, -1
    for i, c in enumerate(sig):
        if c in "([{⟨⦃":
            depth += 1
        elif c in ")]}⟩⦄":
            depth = max(0, depth - 1)
        elif c == ":" and depth == 0 and not sig.startswith(":=", i):
            last = i
    return sig[last + 1:] if last >= 0 else ""


_FIELD_LINE = re.compile(rf"^(\s+)\(?((?:{_COMP}\s+)*{_COMP})\s*(?::(?!=)|\)|$)")
_CTOR = re.compile(rf"^\s*\|\s*({_COMP})")
_CTOR_ANY = re.compile(rf"(?:^|\s)\|\s*({_COMP})", re.M)

TACTICS = {
    # enumeration / kernel computation
    "decide": "enum", "native_decide": "enum", "fin_cases": "enum", "interval_cases": "enum",
    "decide!": "enum",
    # closing automation (routine algebra / search)
    "norm_num": "auto", "omega": "auto", "simp": "auto", "simp_all": "auto", "simpa": "auto",
    "simp_arith": "auto", "dsimp": "auto", "aesop": "auto", "grind": "auto", "tauto": "auto",
    "linarith": "auto", "nlinarith": "auto", "polyrith": "auto", "positivity": "auto",
    "ring": "auto", "ring_nf": "auto", "field_simp": "auto", "gcongr": "auto", "bound": "auto",
    "norm_cast": "auto", "push_cast": "auto", "exact_mod_cast": "auto", "fun_prop": "auto",
    "continuity": "auto", "measurability": "auto", "linear_combination": "auto", "trivial": "auto",
    "abel": "auto", "group": "auto", "noncomm_ring": "auto", "module": "auto", "order": "auto",
    # structural steps
    "intro": "struct", "intros": "struct", "rintro": "struct", "apply": "struct", "exact": "struct",
    "refine": "struct", "refine'": "struct", "use": "struct", "exists": "struct",
    "constructor": "struct", "calc": "struct", "have": "struct", "show": "struct", "obtain": "struct",
    "rcases": "struct", "cases": "struct", "induction": "struct", "cases'": "struct",
    "induction'": "struct", "rw": "struct", "rwa": "struct", "erw": "struct", "nth_rewrite": "struct",
    "ext": "struct", "funext": "struct", "congr": "struct", "convert": "struct", "by_contra": "struct",
    "by_cases": "struct", "split_ifs": "struct", "push_neg": "struct", "contrapose": "struct",
    "contrapose!": "struct", "filter_upwards": "struct", "specialize": "struct", "subst": "struct",
    "unfold": "struct", "exfalso": "struct", "left": "struct", "right": "struct", "set": "struct",
    "suffices": "struct", "let": "struct", "match": "struct", "lift": "struct", "choose": "struct",
    "generalize": "struct", "rel": "struct", "trans": "struct", "symm": "struct",
}
TACTIC_WORDS = set(TACTICS)
_UNINF = re.compile(r"(^|_)(aux|key|step|claim|part|case|lemma|helper|tmp|main|core|sub|foo|bar|"
                    r"technical|auxiliary|basic|fact|thm|lem|prop|cor|piece|chunk|block)(\d*)($|_)", re.I)
_NUMBERED = re.compile(r"(\d+|_[a-z]?\d+[a-z]?)$")


def name_tokens(name: str):
    """Split a (last-component) name into lowercase word tokens, respecting
    snake_case and lowerCamel/UpperCamel. 'IsCompact.exists_forall_le' ->
    ['is','compact','exists','forall','le']."""
    toks = []
    for part in re.split(r"[._']+", name):
        for w in re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+|[^\W\d_]+", part):
            toks.append(w.lower())
    return [t for t in toks if t]


def norm_hash(text: str) -> str:
    return hashlib.blake2b(" ".join(text.split()).encode(), digest_size=8).hexdigest()


def skeleton_hash(text: str) -> str:
    """Hash of the body with every identifier and numeral abstracted: captures
    proofs that are the same template with different names/constants."""
    sk = NUM_RE.sub("0", IDENT_RE.sub(lambda m: m.group() if m.group() in TACTIC_WORDS else "x", text))
    return hashlib.blake2b(" ".join(sk.split()).encode(), digest_size=8).hexdigest()


class Scope:
    __slots__ = ("kind", "ns", "opens", "ncomp")

    def __init__(self, kind, ns, opens, ncomp=0):
        self.kind, self.ns, self.opens, self.ncomp = kind, ns, opens, ncomp


def _opens_from(rest: str):
    names = []
    # take capitalised dotted identifiers outside parentheses, minus keywords
    depth = 0
    for tok in re.findall(rf"\(|\)|{_COMP}(?:\.{_COMP})*", rest):
        if tok == "(":
            depth += 1
        elif tok == ")":
            depth -= 1
        elif depth == 0 and tok not in ("scoped", "hiding", "renaming", "in", "private") and tok[:1].isupper():
            names.append(tok)
    return names


def parse_file(src: str, path: str):
    """Parse one Lean file. Returns (decls, file_info)."""
    text = strip_comments(src)
    scopes = [Scope("root", "", [])]
    decls = []
    pending_attrs = []
    pending_mods = []
    pending_local_opens = []
    file_opens_count = 0
    for line_no, cmd in split_commands(text):
        attrs, i = _consume_attrs(cmd, 0)
        attrs = pending_attrs + attrs
        rest = cmd[i:]
        words = rest.split(None, 1)
        mods = list(pending_mods)
        # strip modifiers
        while words and words[0] in MODIFIERS:
            mods.append(words[0])
            rest = words[1] if len(words) > 1 else ""
            a2, j = _consume_attrs(rest, 0)
            attrs += a2
            rest = rest[j:]
            words = rest.split(None, 1)
        if not words:
            pending_attrs, pending_mods = attrs, mods
            continue
        # a command that is only a prefix ('open X in' on its own line) applies to the next one
        if words[0] in ("open", "variable", "omit", "include", "set_option") and re.search(r"\bin\s*$", rest):
            if words[0] == "open":
                pending_local_opens += _opens_from(re.sub(r"\bin\s*$", "", words[1] if len(words) > 1 else ""))
            pending_attrs, pending_mods = attrs, mods
            continue
        pending_attrs, pending_mods = [], []
        kw = words[0]
        tail = words[1] if len(words) > 1 else ""
        local_opens = pending_local_opens
        pending_local_opens = []
        # 'open X in <cmd>' / 'variable ... in' / 'omit ... in' / 'include ... in' prefixes
        guard = 0
        while kw in ("open", "variable", "omit", "include", "set_option") and re.search(r"\bin\s*\n|\bin\s+(?=@\[|\S)", tail) and guard < 5:
            m = re.search(r"\bin\b", tail)
            head, after = tail[:m.start()], tail[m.end():]
            # only treat as prefix when what follows starts a decl-like command
            nxt_attrs, j = _consume_attrs(after, 0)
            nxt = after[j:].split(None, 1)
            if not nxt or (nxt[0] not in DECL_KINDS and nxt[0] not in MODIFIERS and nxt[0] not in ("open", "variable", "omit", "include", "set_option")):
                break
            if kw == "open":
                local_opens += _opens_from(head)
            attrs += nxt_attrs
            rest = after[j:]
            words = rest.split(None, 1)
            while words and words[0] in MODIFIERS:
                mods.append(words[0])
                rest = words[1] if len(words) > 1 else ""
                words = rest.split(None, 1)
            kw = words[0] if words else ""
            tail = words[1] if len(words) > 1 else ""
            guard += 1

        cur = scopes[-1]
        local_opens = [o for sc in scopes for o in sc.opens] + local_opens
        if kw == "namespace":
            nm = tail.split()[0] if tail.split() else ""
            comps = nm.split(".")
            ns = ".".join(x for x in [cur.ns, nm] if x)
            scopes.append(Scope("namespace", ns, [], len(comps)))
            continue
        if kw == "section" or (kw == "noncomputable" and tail.startswith("section")) or kw == "mutual":
            scopes.append(Scope("section", cur.ns, []))
            continue
        if kw == "end":
            if len(scopes) > 1:
                scopes.pop()
            continue
        if kw == "open" or kw == "export":
            cur.opens.extend(_opens_from(tail))
            file_opens_count += 1
            continue
        if kw not in DECL_KINDS:
            # handle 'class inductive'
            continue
        kind = kw
        if kind == "class" and tail.startswith("inductive"):
            kind = "class_inductive"
            tail = tail[len("inductive"):]
        body_all = tail
        # name
        name = None
        t = body_all.lstrip()
        if kind == "instance":
            t2 = re.sub(r"^\(priority\s*:=\s*[^)]*\)\s*", "", t)
            m = IDENT_RE.match(t2)
            if m and not t2.startswith(("(", "[", "{", ":", "⦃")):
                name = m.group()
                t = t2[m.end():]
            else:
                t = t2
        elif kind == "example":
            pass
        elif kind == "alias":
            m = re.match(rf"⟨\s*([^⟩]*)⟩\s*:=\s*({_COMP}(?:\.{_COMP})*)", t)
            names = []
            target = None
            if m:
                names = [x.strip() for x in m.group(1).split(",") if x.strip() and x.strip() != "_"]
                target = m.group(2)
            else:
                m = re.match(rf"({_COMP}(?:\.{_COMP})*)\s*:=\s*({_COMP}(?:\.{_COMP})*)", t)
                if m:
                    names, target = [m.group(1)], m.group(2)
            for nm in names:
                full = _qualify(cur.ns, nm)
                decls.append(_mk(path, line_no, "alias", full, mods, attrs, "", target or "", cur, local_opens, ""))
            continue
        else:
            m = IDENT_RE.match(t)
            if m:
                name = m.group()
                t = t[m.end():]
        t = re.sub(r"^\.\{[^}]*\}", "", t)  # universe params
        sig, body, sep = _split_top(t)
        full = _qualify(cur.ns, name) if name else None
        d = _mk(path, line_no, kind, full, mods, attrs, sig, body, cur, local_opens, sep)
        decls.append(d)
        # structure fields / inductive constructors -> generated names
        if full and kind in ("structure", "class", "inductive", "class_inductive", "coinductive"):
            gen = [full + s for s in (".mk", ".rec", ".casesOn", ".recOn", ".noConfusion", ".ext", ".ext_iff", ".induct")]
            region = body if sep in ("where", "|") else ""
            if kind in ("inductive", "class_inductive", "coinductive"):
                for c in _CTOR_ANY.findall(sig + "\n" + region):
                    gen += [f"{full}.{c}", f"{full}.{c}.inj", f"{full}.{c}.injEq"]
            else:
                mk = re.search(rf"^\s*({_COMP})\s*::", region, re.M)
                if mk:
                    gen.append(f"{full}.{mk.group(1)}")
                ind = None
                for ln in region.split("\n"):
                    if not ln.strip():
                        continue
                    mm = _FIELD_LINE.match(ln)
                    if not mm:
                        continue
                    w = len(mm.group(1))
                    if ind is None:
                        ind = w
                    if w != ind:
                        continue
                    for f in mm.group(2).split():
                        if f not in ("extends", "mk"):
                            gen.append(f"{full}.{f}")
            d["generated"] = gen
        # to_additive generated name
        for a in attrs:
            if a.strip().startswith("to_additive") or ", to_additive" in a or a.lstrip().startswith("to_additive"):
                if full:
                    explicit = re.search(rf"to_additive(?:\s*\([^)]*\))*\s+(?!existing\b)({_COMP}(?:\.{_COMP})*)", a)
                    d.setdefault("generated", []).append(
                        _qualify(cur.ns, explicit.group(1)) if explicit else to_additive_name(full))
    return decls


def _qualify(ns: str, name: str) -> str:
    if name.startswith("_root_."):
        return name[len("_root_."):]
    return f"{ns}.{name}" if ns else name


def _mk(path, line_no, kind, full, mods, attrs, sig, body, scope: Scope, local_opens, sep):
    # local_opens already contains every open in force (outer scopes + 'open .. in')
    return {
        "path": path, "line": line_no, "kind": kind, "name": full,
        "private": "private" in mods, "attrs": [a.strip() for a in attrs],
        "sig": sig.strip(), "body": body.strip(), "sep": sep,
        "ns": scope.ns, "opens": local_opens,
    }


# --------------------------------------------------- to_additive dictionary --
_ADD_DICT = [
    ("finprod", "finsum"), ("prod", "sum"), ("Prod", "Sum"), ("mul", "add"), ("Mul", "Add"),
    ("one", "zero"), ("One", "Zero"), ("inv", "neg"), ("Inv", "Neg"), ("div", "sub"),
    ("Div", "Sub"), ("zpow", "zsmul"), ("npow", "nsmul"), ("pow", "nsmul"), ("Pow", "SMul"),
    ("smul", "vadd"), ("SMul", "VAdd"), ("monoid", "addMonoid"), ("Monoid", "AddMonoid"),
    ("group", "addGroup"), ("Group", "AddGroup"), ("Semigroup", "AddSemigroup"),
    ("Subgroup", "AddSubgroup"), ("Submonoid", "AddSubmonoid"), ("Units", "AddUnits"),
    ("units", "addUnits"), ("Commute", "AddCommute"), ("commute", "addCommute"),
    ("Torsion", "AddTorsion"), ("orderOf", "addOrderOf"), ("exponent", "exponent"),
    ("lt_one", "neg"),
]


def to_additive_name(full: str) -> str:
    parts = full.split(".")
    out = []
    for p in parts:
        toks = re.split(r"(_)", p)
        new = []
        for tok in toks:
            rep = tok
            for a, b in _ADD_DICT:
                if tok == a:
                    rep = b
                    break
            else:
                # camel prefix replacement: MulAction -> AddAction
                for a, b in _ADD_DICT:
                    if a[:1].isupper() and tok.startswith(a) and len(tok) > len(a) and tok[len(a)].isupper():
                        rep = b + tok[len(a):]
                        break
            new.append(rep)
        out.append("".join(new))
    return ".".join(out)
