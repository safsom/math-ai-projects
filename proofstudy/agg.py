"""Aggregate per-declaration metrics over a set of declarations (a project, a
headline result's dependency cone, or a whole group). One definition, used
everywhere, so project-level and cone-level numbers are the same quantities."""
import numpy as np

METRICS = {
    # key: (family, label, definition)
    "concepts_per_100_thm": ("concept", "Concepts per 100 theorems",
                             "(defs + structures/classes/inductives) per 100 theorem/lemma declarations"),
    "live_concept_share": ("concept", "Live concepts",
                           "share of concepts that appear in the statements of >= 2 theorems in the same corpus"),
    "dead_concept_share": ("concept", "Dead concepts", "share of concepts referenced by nothing in the corpus"),
    "single_use_lemma_share": ("concept", "Single-use lemmas",
                               "share of theorems/lemmas cited by exactly one other declaration"),
    "reusable_lemma_share": ("concept", "Reusable lemmas", "share of theorems/lemmas cited by >= 3 declarations"),
    "cert_token_share": ("brute", "Certificate mass",
                         "share of all proof/definition tokens in declarations that are numeral-dense "
                         "(>= 25% numerals, >= 50 tokens) or use decide/native_decide"),
    "casebash_token_share": ("brute", "Case-bash mass",
                             "share of theorem proof tokens in proofs that enumerate cases (fin_cases / "
                             "interval_cases) and close them uniformly (<;>, all_goals or decide)"),
    "enum_per_1k": ("brute", "Enumeration tactics / 1k tokens", "decide, native_decide, fin_cases, interval_cases"),
    "auto_per_1k": ("brute", "Closing automation / 1k tokens",
                    "simp, omega, linarith, nlinarith, norm_num, positivity, ring, aesop, grind, ..."),
    "struct_per_1k": ("brute", "Structural steps / 1k tokens",
                      "intro, apply, exact, refine, have, obtain, calc, induction, rw, ..."),
    "numeral_density": ("brute", "Numeral density", "numeric literals per proof token"),
    "name_tokens": ("naming", "Words per theorem name", "median number of words in theorem names"),
    "numbered_share": ("naming", "Numbered names", "theorem names ending in / containing serial numbers (cover12, step_3)"),
    "uninformative_share": ("naming", "Placeholder names",
                            "theorem names built on aux/key/step/claim/main/helper/part/... words"),
    "vocab_share": ("naming", "Mathlib vocabulary",
                    "share of theorem-name words that occur >= 5 times in mathlib theorem names"),
    "grounding": ("naming", "Name grounding",
                  "share of a theorem name's words found in the names of the constants its statement mentions"),
    "ns_inherit": ("naming", "Namespace inheritance",
                   "share of theorems whose namespace is the name of a constant in their statement (dot-notation ready)"),
    "propagation": ("naming", "Concept-name propagation",
                    "for concepts used in >= 2 theorem statements: share of those theorems whose name contains the concept's name"),
    "proof_to_statement": ("compression", "Proof / statement length", "median theorem proof tokens / statement tokens"),
    "body_dup_share": ("compression", "Duplicate proofs",
                       "share of theorem proofs (>= 20 tokens) whose exact text occurs again in the corpus"),
    "skel_dup_share": ("compression", "Template proofs",
                       "share of theorem proofs (>= 30 tokens) whose identifier-abstracted skeleton occurs again"),
    "zlib_ratio": ("compression", "zlib ratio", "compressed/raw size on fixed 32 KiB windows (lower = more repetitive)"),
    "library_ref_share": ("derivation", "Library references",
                          "share of resolved references (distinct per declaration) that go to mathlib/core/batteries"),
    "stmt_library_share": ("derivation", "Statements in library terms",
                           "share of statement-level references that are mathlib/core/batteries constants"),
    "reinvent_share": ("derivation", "Restated mathlib theorems",
                       "share of theorem statements (>= 8 tokens) identical, after alpha-normalisation, to a mathlib statement"),
    "cross_project_restatement": ("derivation", "Re-derived across projects",
                                  "share of theorem statements that recur verbatim (alpha-normalised) in another project"),
}


def summarize(c, head_row=None):
    """c: DataFrame of per-declaration metrics for one unit."""
    thm = c[c.is_thm.values]
    lem = thm.drop(index=head_row, errors="ignore") if head_row is not None else thm
    conc = c[c.is_concept.values]
    tok = float(c.n_body_tok.sum())
    ttok = float(thm.n_body_tok.sum())
    refs = float(c.refs_own.sum() + c.refs_lib.sum() + c.refs_other.sum())
    pu = float(conc.prop_users.fillna(0).sum())
    sl, so = float(c.sig_refs_lib.sum()), float(c.sig_refs_own.sum())
    se = float(thm.sig_eligible.sum())
    nan = np.nan
    return dict(
        n_decls=len(c), n_thm=len(thm), n_concepts=len(conc), tokens=tok,
        concepts_per_100_thm=100 * len(conc) / len(thm) if len(thm) else nan,
        live_concept_share=(conc.n_thm_stmt_users.values >= 2).mean() if len(conc) else nan,
        dead_concept_share=(conc.n_users.values == 0).mean() if len(conc) else nan,
        single_use_lemma_share=(lem.n_users.values == 1).mean() if len(lem) else nan,
        reusable_lemma_share=(lem.n_users.values >= 3).mean() if len(lem) else nan,
        cert_token_share=c.n_body_tok.values[c.cert_25.values].sum() / tok if tok else nan,
        casebash_token_share=thm.n_body_tok.values[thm.casebash.values].sum() / ttok if ttok else nan,
        enum_per_1k=1000 * c.t_enum.sum() / tok if tok else nan,
        auto_per_1k=1000 * c.t_auto.sum() / tok if tok else nan,
        struct_per_1k=1000 * c.t_struct.sum() / tok if tok else nan,
        numeral_density=c.n_num.sum() / tok if tok else nan,
        name_tokens=float(np.median(thm.n_name_tok.values)) if len(thm) else nan,
        numbered_share=thm.numbered.mean() if len(thm) else nan,
        uninformative_share=thm.uninformative.mean() if len(thm) else nan,
        vocab_share=thm.vocab_share.mean() if len(thm) else nan,
        grounding=thm.grounding.mean() if len(thm) else nan,
        ns_inherit=thm.ns_inherit.mean() if len(thm) else nan,
        propagation=conc.prop_hits.fillna(0).sum() / pu if pu else nan,
        proof_to_statement=float(np.median(thm.n_body_tok.values / np.maximum(thm.n_sig_tok.values, 1))) if len(thm) else nan,
        body_dup_share=thm.body_dup.sum() / thm.body_dup_eligible.sum() if thm.body_dup_eligible.sum() else nan,
        skel_dup_share=thm.skel_dup.sum() / thm.skel_dup_eligible.sum() if thm.skel_dup_eligible.sum() else nan,
        library_ref_share=c.refs_lib.sum() / refs if refs else nan,
        stmt_library_share=sl / (sl + so) if (sl + so) else nan,
        reinvent_share=thm.reinvents_mathlib.sum() / se if se else nan,
        reinvent_n=int(thm.reinvents_mathlib.sum()),
        cross_project_restatement=thm.sig_dup_cross_project.sum() / se if se else nan,
        unresolved_per_decl=c.n_unresolved_q.mean(),
        dot_resolved_per_decl=c.n_dot_resolved.mean() if "n_dot_resolved" in c else nan,
    )
