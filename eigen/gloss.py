"""Plain-language descriptions of typed gestures."""
import re

GLOSS_CORE = {
    'Eq.mpr': 'rewrite the goal along an equation', 'Eq.mp': 'rewrite a fact along an equation',
    'congrArg': 'apply a function to both sides', 'congrFun': 'evaluate both sides at a point',
    'congr': 'equal functions at equal arguments', 'Eq.trans': 'chain two equalities',
    'Eq.symm': 'flip an equation', 'of_eq_true': 'close a goal that simp reduced to True',
    'eq_self': 'a = a is True', 'propext': 'turn an iff into an equality', 'id': 'restate the goal (show)',
    'Eq.refl': 'reflexivity', 'rfl': 'reflexivity', 'And.intro': 'prove both halves of a conjunction',
    'Exists.intro': 'exhibit a witness', 'absurd': 'derive anything from P and not P',
    'False.elim': 'derive anything from False', 'Classical.byContradiction': 'assume the negation',
    'Or.elim': 'split on a disjunction', 'Or.inl': 'prove the left disjunct', 'Or.inr': 'prove the right disjunct',
    'Iff.intro': 'prove both directions', 'Iff.mp': 'use an iff forwards', 'Iff.mpr': 'use an iff backwards',
    'funext': 'prove functions equal pointwise', 'Eq.ndrec': 'transport along an equation (▸)',
    'dite': 'split on a decidable condition', 'implies_congr': 'rewrite inside an implication',
    'forall_congr': 'rewrite under a binder', 'And.left': 'take the left half of a conjunction',
    'And.right': 'take the right half of a conjunction', 'Exists.elim': 'unpack an existential',
    'Classical.byCases': 'split on whether a proposition holds', 'Not.intro': 'prove a negation',
    'letFun': 'state an intermediate claim', 'le_refl': 'x ≤ x', 'le_rfl': 'x ≤ x', 'trivial': 'True',
    'Subtype.property': 'use the property of a subtype element', 'ne_eq': 'unfold ≠', 'eq_true': 'P is True',
    'eq_false': 'P is False', 'of_eq_false': 'close a goal that simp reduced to False',
    'not_false_eq_true': '¬False is True', 'iff_of_eq': 'turn an equality of props into an iff',
}
GLOSS_TAC = {'Ring': 'ring-normalization certificate', 'Linarith': 'linarith certificate',
             'NormNum': 'norm_num numeral evaluation', 'Positivity': 'positivity certificate',
             'Omega': 'omega certificate', 'FieldSimp': 'field_simp step', 'Abel': 'abel normalization',
             'Grind': 'grind certificate', 'IntArith': 'integer-arithmetic certificate (omega or lia)', 'Linear': 'linear-arithmetic normalization',
             'Aesop': 'aesop step', 'Polyrith': 'polyrith certificate', 'GCongr': 'gcongr step',
             'Bound': 'bound certificate', 'NormCast': 'norm_cast step', 'Monotonicity': 'monotonicity step'}


TY = {'P': 'predicate'}
USE = {"0": "never used", "1": "used once", "ω": "used repeatedly"}


def describe(g):
    if g == '(other gestures)':
        return 'all rarer gestures together'
    m = re.match(r'λh:(.*):([01ω])$', g)
    if m:
        return f'assume a {TY.get(m.group(1), m.group(1))} hypothesis, {USE[m.group(2)]}'
    m = re.match(r'λx:([01ω])$', g)
    if m:
        return f'take an arbitrary element, {USE[m.group(1)]}'
    m = re.match(r'cut:(.*):([01ω])$', g)
    if m:
        return f'state an intermediate {TY.get(m.group(1), m.group(1))} claim, {USE[m.group(2)]}'
    if g == 'let':
        return 'introduce a local definition'
    if g == 'cut:β':
        return 'apply a function to its argument on the spot (an inline show … from or let)'
    if g == 'proj:struct':
        return 'project a field out of a structure'
    m = re.match(r'^([^()]+)\((.*)\)⇒(.*)$', g)
    if not m:
        return g
    mech, prem, concl = m.groups()
    prem_s = f' from ({prem})' if prem else ''
    if mech.startswith('core:'):
        base = GLOSS_CORE.get(mech[5:], mech[5:])
        return f'{base}{prem_s} ⇒ {concl}'
    if mech.startswith('tac:'):
        return f'{GLOSS_TAC.get(mech[4:], mech[4:] + " step")}{prem_s} ⇒ {concl}'
    if mech == 'lemma':
        return f'apply a lemma{prem_s} ⇒ {concl}'
    if mech == 'hyp':
        return f'apply a hypothesis{prem_s} ⇒ {concl}' if prem else f'use a hypothesis ⇒ {concl}'
    if mech == 'rec':
        return f'induction / recursion{prem_s} ⇒ {concl}'
    if mech == 'match':
        return f'pattern-match{prem_s} ⇒ {concl}'
    if mech.startswith('decide'):
        return f'decide by computation ⇒ {concl}'
    if mech == 'ctor':
        return f'build with a constructor{prem_s} ⇒ {concl}'
    if mech == 'def':
        return f'unfold a definition{prem_s} ⇒ {concl}'
    return g


