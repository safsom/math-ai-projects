"""Size-controlled compressibility per project.

Raw zlib ratios depend on text length, so each project's comment-stripped source
is cut into fixed 32 KiB windows (up to 64 evenly spaced windows per project) and
the mean compressed/raw ratio is reported. Lower = more repetitive text.
Projects with less than one full window are reported as NaN.
"""
import sys
import zlib
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from extract import CORPORA, corpus_files  # noqa: E402
from leanparse import strip_comments  # noqa: E402

W = 32 * 1024
rows = []
for corpus, cfg in CORPORA.items():
    if cfg["role"] == "base":
        continue
    texts = defaultdict(list)
    for f in corpus_files(corpus):
        t = strip_comments(open(f, encoding="utf-8", errors="replace").read())
        t = "\n".join(l.rstrip() for l in t.split("\n") if l.strip())
        texts[cfg["project"](f)].append(t)
    for proj, ts in texts.items():
        b = "\n".join(ts).encode()
        nwin = len(b) // W
        if nwin == 0:
            rows.append((corpus, proj, len(b), float("nan"), 0))
            continue
        step = max(1, nwin // 64)
        rs = [len(zlib.compress(b[i * W:(i + 1) * W], 6)) / W for i in range(0, nwin, step)][:64]
        rows.append((corpus, proj, len(b), sum(rs) / len(rs), len(rs)))
    print(corpus, len(texts), flush=True)
pd.DataFrame(rows, columns=["corpus", "project", "bytes", "zlib_ratio", "windows"]).to_csv(sys.argv[1], index=False)
