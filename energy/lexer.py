"""Syntactic Lean 4 lexer: strip comments/strings, split files into declarations,
tokenize, and split identifiers into mathlib-style pieces for the energy model."""
import math
import re

DECL_KW = r"(?:theorem|lemma|def|abbrev|instance|example|structure|class|inductive|opaque|axiom|irreducible_def)"
MODS = r"(?:(?:private|protected|noncomputable|nonrec|partial|unsafe|scoped|local)\s+)*"
# A command starts at column 0. Attribute blocks may sit on their own lines before the keyword.
DECL_START = re.compile(rf"^(?:@\[[^\n]*\]\s*)*{MODS}(?:{DECL_KW})\b", re.M)
CMD_START = re.compile(
    r"^(?:@\[|(?:private|protected|noncomputable|nonrec|partial|unsafe|scoped|local)\s|"
    r"theorem\b|lemma\b|def\b|abbrev\b|instance\b|example\b|structure\b|class\b|inductive\b|opaque\b|"
    r"axiom\b|irreducible_def\b|namespace\b|section\b|end\b|open\b|variable\b|universe\b|set_option\b|"
    r"attribute\b|notation\b|infix|prefix|postfix|macro\b|syntax\b|elab\b|import\b|noncomputable section|"
    r"local\b|scoped\b|initialize\b|run_cmd\b|#|mutual\b|deriving\b|alias\b|omit\b|include\b|suppress_compilation|"
    r"compile_inductive|add_decl_doc|library_note|assert_not_exists|unseal\b|seal\b|termination_by|decreasing_by)",
    re.M,
)

_COMMENT_STR = re.compile(r'--[^\n]*|"(?:[^"\\]|\\.)*"', re.S)


def strip_comments(src: str) -> str:
    """Remove nested block comments, line comments and string literals (keeps newlines)."""
    out = []
    i, n = 0, len(src)
    depth = 0
    start = 0
    while i < n:
        if depth == 0:
            j = src.find("/-", i)
            if j < 0:
                out.append(src[start:])
                break
            out.append(src[start:j])
            depth = 1
            i = j + 2
        else:
            a = src.find("/-", i)
            b = src.find("-/", i)
            if b < 0:
                break
            if 0 <= a < b:
                depth += 1
                i = a + 2
            else:
                depth -= 1
                i = b + 2
                if depth == 0:
                    out.append("\n" * 0)
                    start = i
    s = "".join(out)
    return _COMMENT_STR.sub(lambda m: "" if m.group(0).startswith("--") else '""', s)


ID_START = r"[^\W\dλΠΣ]|_"
ID_CONT = r"[\w'!?₀-ₜᵢ-ᵪⱼ]"
IDENT = rf"(?:«[^»]*»|(?:{ID_START}){ID_CONT}*)"
TOKEN_RE = re.compile(
    rf"(?P<id>{IDENT}(?:\.{IDENT})*)"
    r"|(?P<num>0[xX][0-9a-fA-F_]+|0[bB][01_]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
    r"|(?P<op><;>|:=|=>|->|<-|<->|\.\.\.|\.\.|::|\|\||&&|<=|>=|!=|==|\^\^|\+\+|\$|<\||\|>|·|\S)"
)
LONGNUM_DIGITS = 4  # numerals with this many digits or more are coded digit-by-digit


def tokenize(text: str):
    """Yield (kind, token) with kind in {'id','num','op'}."""
    for m in TOKEN_RE.finditer(text):
        k = m.lastgroup
        yield k, m.group(k)


_CAMEL = re.compile(r"[._]?[A-Z]?[a-zα-ω']+[₀-₉]*|[._]?[A-Z]+(?![a-z])[₀-₉]*|[._]?\d+|[._]?.")


def split_ident(tok: str):
    """`Finset.sum_le_sum` -> ['Finset', '.sum', '_le', '_sum']."""
    pieces = []
    for i, part in enumerate(tok.split(".")):
        sub = part.split("_")
        first = True
        for s in sub:
            if first:
                p = s if i == 0 else "." + s
                first = False
            else:
                p = "_" + s
            if p not in ("", "_", "."):
                # camelCase words become separate pieces; '^' marks a joined word
                words = _CAMEL.findall(p)
                if len(words) > 1 and "".join(words) == p:
                    pieces.append(words[0])
                    pieces.extend("^" + w for w in words[1:])
                else:
                    pieces.append(p)
            elif p == "_" and len(sub) > 1:
                pieces.append("_")
    return pieces or [tok]


def literal_bits(numtok: str) -> float:
    """Cost of spelling out a long numeral: its digits plus an Elias-gamma-style length code."""
    d = sum(c.isalnum() for c in numtok)
    return d * math.log2(10) + 2 * math.log2(d) + 1


def lm_tokens(text: str):
    """Tokens fed to the language model, plus the literal-channel bits and token-class labels.

    Returns (tokens, classes, literal_bits_total). Class: n=name piece, k=numeral, o=operator/punct.
    """
    toks, cls = [], []
    lit = 0.0
    for kind, t in tokenize(text):
        if kind == "id":
            ps = split_ident(t)
            toks.extend(ps)
            cls.extend("n" * len(ps))
        elif kind == "num":
            digits = sum(c.isdigit() for c in t)
            if digits >= LONGNUM_DIGITS:
                toks.append("<longnum>")
                lit += literal_bits(t)
            else:
                toks.append(t)
            cls.append("k")
        else:
            toks.append(t)
            cls.append("o")
    return toks, cls, lit


KEYWORD_OF = re.compile(rf"\b({DECL_KW})\b")
_DEPTH_OPEN = "([{⟨⦃"
_DEPTH_CLOSE = ")]}⟩⦄"


def split_statement_proof(decl: str):
    """Split at the first `:=` / ` where` / newline-`|` at bracket depth 0."""
    depth = 0
    i, n = 0, len(decl)
    while i < n:
        c = decl[i]
        if c in _DEPTH_OPEN:
            depth += 1
        elif c in _DEPTH_CLOSE:
            depth -= 1
        elif depth <= 0:
            if decl.startswith(":=", i):
                return decl[:i], decl[i + 2:]
            if decl.startswith(" where", i) and (i + 6 == n or not decl[i + 6].isalnum()):
                return decl[:i], decl[i + 6:]
            if c == "|" and i > 0 and decl[i - 1] == "\n" or (c == "|" and decl[max(0, i - 2):i] == "\n "):
                return decl[:i], decl[i:]
        i += 1
    return decl, ""


_NS = re.compile(r"^(namespace|section|end|open|noncomputable section)\b([^\n]*)", re.M)


def declarations(src: str):
    """Yield dicts for each declaration in a (comment-stripped) file.

    Keys: kind, name, namespace (list), opens (list), text, statement, proof.
    """
    cmd_starts = [m.start() for m in CMD_START.finditer(src)] + [len(src)]
    ns_stack = []  # entries: ("ns", name) | ("sec", name)
    opens_stack = [[]]
    for a, b in zip(cmd_starts, cmd_starts[1:]):
        chunk = src[a:b]
        head = chunk[:200]
        m = _NS.match(head)
        if m:
            kw, rest = m.group(1), m.group(2).strip()
            if kw == "namespace":
                for part in rest.split(".") if rest else []:
                    ns_stack.append(("ns", part))
                    opens_stack.append(list(opens_stack[-1]))
            elif kw in ("section", "noncomputable section"):
                ns_stack.append(("sec", rest))
                opens_stack.append(list(opens_stack[-1]))
            elif kw == "end":
                name = rest.split()[0] if rest else ""
                k = len(name.split(".")) if name and ns_stack and ns_stack[-1][0] == "ns" else 1
                for _ in range(k):
                    if ns_stack:
                        ns_stack.pop()
                        if len(opens_stack) > 1:
                            opens_stack.pop()
            elif kw == "open":
                if " in" not in rest and not rest.endswith("in"):
                    opens_stack[-1].extend(x for x in re.split(r"[\s()]+", rest.replace("scoped", ""))
                                           if x and x[0].isalpha() and x not in ("hiding", "renaming", "in"))
            continue
        dm = DECL_START.match(chunk)
        if not dm:
            continue
        kwm = KEYWORD_OF.search(chunk, 0, dm.end())
        kind = kwm.group(1) if kwm else "def"
        after = chunk[dm.end():].lstrip()
        nm = re.match(rf"{IDENT}(?:\.{IDENT})*", after)
        name = nm.group(0) if nm and kind not in ("example",) else ""
        if kind == "instance" and name in ("", ":") or name in ("where", "with"):
            name = ""
        ns = [x[1] for x in ns_stack if x[0] == "ns"]
        stmt, proof = split_statement_proof(chunk[dm.end():])
        yield {
            "kind": kind,
            "name": name,
            "namespace": ns,
            "opens": list(opens_stack[-1]),
            "text": chunk.strip(),
            "statement": stmt,
            "proof": proof,
        }
