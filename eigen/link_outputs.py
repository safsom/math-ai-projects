"""Link the final pass's records into the directories the analyses read.

The final pass (run_all.sh) writes out_terms_v4/ (mathlib, OpenAI, human), out_terms_v4_iso/ (the OpenAI projects
compiled module by module) and out_terms_v4_ai/<corpus>/ (sphere packing, Putnam, IMO). Its records carry the
gestures, the cut sizes and the proof-term measures together. The gesture analyses read out_final/, the cut analyses
out_cut/, and the other AI corpora are read from out_ai/<corpus>/. Existing files are left alone.
Usage: python3 link_outputs.py [RUN_DIR]   (default: this directory)
"""
import glob, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else HERE


def link(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not os.path.exists(dst) and not os.path.islink(dst):
        os.symlink(src, dst)


for f in glob.glob(os.path.join(RUN, 'out_terms_v4', '*.jsonl')):
    if f.endswith(('.log.jsonl', '.trace.jsonl')) or os.path.basename(f).startswith('trace_'):
        continue
    for d in ('out_final', 'out_cut'):
        link(f, os.path.join(HERE, d, os.path.basename(f)))
for f in glob.glob(os.path.join(RUN, 'out_terms_v4_ai', '*', '*.jsonl')):
    c = os.path.basename(os.path.dirname(f))
    link(f, os.path.join(HERE, 'out_ai', c, os.path.basename(f)))
for d in ('out_terms_v4', 'out_terms_v4_iso', 'out_terms_v4_ai'):
    if RUN != HERE and os.path.isdir(os.path.join(RUN, d)):
        link(os.path.join(RUN, d), os.path.join(HERE, d))
print('linked')
