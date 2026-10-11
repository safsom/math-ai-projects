"""Walk every corpus, split files into declarations, and save per-project samples.

Output: data/decls_<corpus>.pkl with
  projects: list of per-project summaries (all declarations counted)
  decls:    sampled declarations (<= CAP per project) with text, statement, proof, scope info
  names:    every declared full name per project (for local-name resolution)
"""
import os
import pickle
import random
import re
import sys
from collections import defaultdict
from multiprocessing import Pool

from lexer import declarations, strip_comments

ROOT = "/Users/safsom/Projects/math-ai-projects"
CAP = 1000
SEED = 20261009

CORPORA = {
    "mathlib": (f"{ROOT}/mathlib4", "Mathlib", 2),
    "openai": (f"{ROOT}/corpora/openai_math/lean", "OAI", 2),
    "tenproofs": (f"{ROOT}/corpora/openai_ten-proofs", "", 0),
    "carleson": (f"{ROOT}/corpora/fpvandoorn_carleson", "Carleson", 1),
    "flt": (f"{ROOT}/corpora/ImperialCollegeLondon_FLT", "FLT", 1),
    "pfr": (f"{ROOT}/corpora/teorth_pfr", "PFR", 1),
    "sphere": (f"{ROOT}/corpora/leanprover-community_sphere-eversion", "SphereEversion", 1),
    "strongpnt": (f"{ROOT}/corpora/math-inc_strongpnt", "StrongPNT", 0),
    # other AI-written corpora (same project definitions as eigen/analyze.py)
    "ai_flt": (f"{ROOT}/corpora/ai/flt", "", 0),
    "ai_spherepacking": (f"{ROOT}/corpora/ai/Sphere-Packing-Lean", "SpherePacking", 1),
    "ai_erdos90": (f"{ROOT}/corpora/ai/Erdos90/src/original", "Towers", 1),
    "ai_putnam2025": (f"{ROOT}/corpora/ai/Putnam2025", "Putnam2025", 1),
    "ai_imo2025": (f"{ROOT}/corpora/ai/IMO2025", "HarmonicLean", 1),
}
SKIP = re.compile(r"/(\.lake|blueprint|test|tests|docs|scripts|Archive|Counterexamples|MathlibTest|\.github)/|lakefile")

CERT_PROOF = re.compile(r"\bnative_decide\b|\bdecide\s*\+kernel\b|\bdecide\s*\(config|\bby\s+decide\b")
NUM = re.compile(r"\d+")


def project_of(corpus, rel):
    base, top, depth = CORPORA[corpus]
    parts = rel.split("/")
    if corpus == "tenproofs":
        return parts[0].removesuffix(".lean")
    if corpus == "strongpnt":
        return "StrongPNT"
    if corpus == "ai_flt":
        # proofs and definitions, by the area in the file name; Theorems/ holds statement wrappers
        if parts[0] not in ("P2M", "Definitions") or parts[-1] == "Util.lean":
            return None
        stem = parts[-1].removesuffix(".lean")
        stem = stem.split("_", 1)[1] if "_" in stem else stem
        return "flt/" + stem.split("_")[0]
    if not top or parts[0] != top:
        return None
    rest = parts[1:]
    if len(rest) <= depth:  # file sits above project depth
        return "/".join([top] + rest[:-1] + ["_root"])
    return "/".join([top] + rest[:depth])


def list_files(corpus):
    base = CORPORA[corpus][0]
    out = defaultdict(list)
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if not d.startswith(".")]
        for f in fn:
            if f.endswith(".lean"):
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, base)
                if SKIP.search("/" + rel):
                    continue
                proj = project_of(corpus, rel)
                if proj:
                    out[proj].append(rel)
    return out


def is_certificate(d):
    """Numeral-dense declaration, or kernel computation via decide (the dashboard's definition)."""
    t = d["text"]
    digits = sum(len(x) for x in NUM.findall(t))
    long_num = any(len(x) >= 4 for x in NUM.findall(t))
    if digits >= 0.25 * max(1, len(t) - t.count(" ")) and digits >= 20:
        return True
    return bool(CERT_PROOF.search(d["proof"])) and long_num


def process_project(args):
    corpus, proj, files = args
    base = CORPORA[corpus][0]
    rng = random.Random(f"{SEED}:{corpus}:{proj}")
    sample, seen = [], 0
    names = []
    s = dict(corpus=corpus, project=proj, n_files=len(files), n_decls=0, n_thm=0, n_def=0,
             chars=0, cert_chars=0, cert_decls=0)
    for rel in sorted(files):
        try:
            src = open(os.path.join(base, rel), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        src = strip_comments(src)
        for d in declarations(src):
            full = ".".join(d["namespace"] + [d["name"]]) if d["name"] else ""
            d["full"] = full
            d["file"] = rel
            if d["name"].startswith("_root_."):
                d["full"] = d["name"][len("_root_."):]
            if d["full"]:
                names.append(d["full"])
            cert = is_certificate(d)
            n = len(d["text"])
            s["n_decls"] += 1
            s["chars"] += n
            if d["kind"] in ("theorem", "lemma"):
                s["n_thm"] += 1
            elif d["kind"] in ("def", "abbrev", "structure", "class", "inductive", "irreducible_def", "opaque"):
                s["n_def"] += 1
            if cert:
                s["cert_chars"] += n
                s["cert_decls"] += 1
            d["cert"] = cert
            d["corpus"], d["project"] = corpus, proj
            seen += 1
            if len(sample) < (10**9 if corpus == "mathlib" else CAP):
                sample.append(d)
            else:  # reservoir sampling keeps a uniform sample of declarations
                j = rng.randrange(seen)
                if j < CAP:
                    sample[j] = d
    return s, sample, names


def main(corpora):
    os.makedirs(f"{ROOT}/energy/data", exist_ok=True)
    for corpus in corpora:
        files = list_files(corpus)
        jobs = sorted(((corpus, p, fs) for p, fs in files.items()), key=lambda j: -len(j[2]))
        projects, decls, names = [], [], {}
        with Pool(int(os.environ.get("NPROC", 6))) as pool:
            for s, sample, nm in pool.imap_unordered(process_project, jobs, chunksize=1):
                projects.append(s)
                decls.extend(sample)
                names[s["project"]] = nm
        with open(f"{ROOT}/energy/data/decls_{corpus}.pkl", "wb") as f:
            pickle.dump(dict(projects=projects, decls=decls, names=names), f)
        print(corpus, "projects", len(projects), "decls", sum(p["n_decls"] for p in projects),
              "sampled", len(decls), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or list(CORPORA))
