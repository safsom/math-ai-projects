"""Pooled metrics for OpenAI's two regimes: projects whose certificate mass is
>= 30% ('certificate shell') vs the rest ('conceptual core'), with controls."""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from agg import summarize
EXT, RES = Path(sys.argv[1]), Path(sys.argv[2])
P = pd.read_csv(RES / "project_metrics.csv")
shell = set(P[(P.group == "openai_math") & (P.cert_token_share >= 0.3)].project)
cols = ["corpus", "group", "project", "is_thm", "is_concept", "n_body_tok", "n_sig_tok", "n_users", "n_thm_stmt_users",
        "t_enum", "t_auto", "t_struct", "n_num", "cert_25", "casebash", "grounding", "numbered", "uninformative",
        "vocab_share", "n_name_tok", "ns_inherit", "refs_own", "refs_lib", "refs_other", "sig_refs_own", "sig_refs_lib",
        "body_dup", "body_dup_eligible", "skel_dup", "skel_dup_eligible", "reinvents_mathlib", "sig_dup_cross_project",
        "sig_eligible", "prop_users", "prop_hits", "n_unresolved_q", "n_dot_resolved"]
df = pd.read_parquet(EXT / "metrics.parquet", columns=cols)
o = df[df.group == "openai_math"]
rows = []
isshell = o.project.isin(shell).values
for lab, sub in (("openai_core", o[~isshell]), ("openai_shell", o[isshell]),
                 ("human_research", df[df.group == "human_research"]), ("mathlib", df[df.group == "mathlib"])):
    s = summarize(sub); s["stratum"] = lab; s["n_projects"] = sub.project.nunique(); rows.append(s)
pd.DataFrame(rows).to_csv(RES / "strata_pooled.csv", index=False)
print(pd.DataFrame(rows).set_index("stratum")[["n_projects", "n_decls", "tokens", "cert_token_share", "numbered_share",
      "skel_dup_share", "concepts_per_100_thm", "live_concept_share", "single_use_lemma_share", "grounding",
      "propagation", "library_ref_share", "vocab_share", "cross_project_restatement"]].round(3).T.to_string())
