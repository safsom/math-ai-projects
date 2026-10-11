UPSTREAM = {'Mathlib', 'ToMathlib', 'ForMathlib'}


def group_of(corpus, project):
    if corpus in ('mathlib', 'openai', 'strongpnt'):
        return corpus
    if corpus == 'tenproofs':
        return 'openai-ten'
    return 'human-upstream' if project.split('/')[-1] in UPSTREAM else 'human'
