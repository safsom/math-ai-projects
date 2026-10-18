"""Figures for report.tex. Reads the result files directly; run from the repo root:
    python3 report/figures/make_figures.py
Writes PDFs next to this script.
"""
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.dirname(os.path.abspath(__file__))
EG = os.path.join(ROOT, 'eigen')

# Fixed categorical order (validated default palette, slots 1-4); mathlib is the reference, in neutral grey.
COL = {'openai': '#2a78d6', 'human': '#eb6834', 'spherepacking': '#1baf7a', 'putnam2025': '#eda100',
       'mathlib': '#8a8984'}
NAME = {'mathlib': 'mathlib', 'human': 'human research', 'openai': 'OpenAI',
        'spherepacking': 'sphere packing', 'putnam2025': 'Putnam 2025', 'human-upstream': 'human, for mathlib'}
INK, INK2, GRID = '#0b0b0b', '#52514e', '#e4e3df'

plt.rcParams.update({
    'font.family': 'serif', 'font.serif': ['Computer Modern Roman', 'CMU Serif', 'DejaVu Serif'],
    'mathtext.fontset': 'cm', 'font.size': 9, 'axes.titlesize': 9, 'axes.labelsize': 9,
    'xtick.labelsize': 8, 'ytick.labelsize': 8, 'legend.fontsize': 8,
    'axes.edgecolor': INK2, 'axes.labelcolor': INK, 'xtick.color': INK2, 'ytick.color': INK2,
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.linewidth': 0.6,
    'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.5, 'axes.axisbelow': True,
    'legend.frameon': False, 'pdf.fonttype': 42, 'savefig.bbox': 'tight', 'savefig.pad_inches': 0.02,
})


def save(fig, name):
    fig.savefig(os.path.join(OUT, name))
    plt.close(fig)
    print('wrote', name)


def text_energy():
    """Per-project text energy under mathlib's 5-gram model."""
    P = pd.read_csv(os.path.join(ROOT, 'energy', 'data', 'out', 'projects.csv'))
    groups = ['mathlib', 'human-upstream', 'human', 'openai']
    rng = np.random.default_rng(0)
    fig, ax = plt.subplots(figsize=(5.6, 2.1))
    for i, g in enumerate(groups):
        v = P[P.group == g].e_tok.clip(upper=11).values
        y = i + rng.uniform(-0.28, 0.28, len(v))
        c = COL.get(g, COL['human'] if g.startswith('human') else INK2)
        ax.scatter(v, y, s=9, color=c, alpha=0.55 if len(v) > 50 else 0.9, linewidths=0)
        m = np.median(P[P.group == g].e_tok)
        ax.plot([m, m], [i - 0.38, i + 0.38], color=INK, lw=1.4)
        ax.text(11.15, i, f'{m:.2f}', va='center', fontsize=8, color=INK)
    ax.set_yticks(range(len(groups)))
    ax.set_yticklabels([f'{NAME[g]} ({(P.group == g).sum()})' for g in groups])
    ax.set_xlim(4, 11)
    ax.set_xlabel('bits per token under a 5-gram model of mathlib')
    ax.grid(axis='y', visible=False)
    save(fig, 'text_energy.pdf')


def spectrum():
    """OpenAI's eigenproof bits against the size-matched null."""
    R = json.load(open(os.path.join(EG, 'out_final', 'analysis_merged', 'results.json')))
    k = 12
    bits = [s['bits'] for s in R['spectrum']['openai'][:k]]
    med, mx = R['null']['top_median'][:k], R['null']['top_max'][:k]
    x = np.arange(1, k + 1)
    fig, ax = plt.subplots(figsize=(5.6, 2.2))
    ax.bar(x, bits, width=0.62, color=COL['openai'], label='OpenAI vs mathlib')
    ax.step(np.r_[x - 0.5, x[-1] + 0.5], np.r_[med, med[-1]], where='post', color=INK, lw=1.0,
            label='null, median of 10 draws')
    ax.step(np.r_[x - 0.5, x[-1] + 0.5], np.r_[mx, mx[-1]], where='post', color=INK, lw=0.8, ls='--',
            label='null, maximum')
    ax.set_xticks(x)
    ax.set_xlabel('eigenproof (rank)')
    ax.set_ylabel('bits')
    ax.grid(axis='x', visible=False)
    ax.legend(loc='upper right')
    save(fig, 'spectrum.pdf')


def chi_rho():
    """Per-project mean compressibility and redundancy."""
    C = json.load(open(os.path.join(EG, 'out_cut', 'results_ai.json')))
    fig, ax = plt.subplots(figsize=(4.4, 3.4))
    lim = 0.3
    ax.plot([0, lim], [0, lim], color=INK2, lw=0.7, ls=':')
    ax.text(0.205, 0.235, r'$\kappa=0$', color=INK2, fontsize=8, rotation=37)
    ax.text(0.012, 0.27, 'proof larger with its cuts', color=INK2, fontsize=7.5)
    ax.text(0.17, 0.012, 'cuts save space', color=INK2, fontsize=7.5)
    for g in ['mathlib', 'human', 'openai', 'spherepacking', 'putnam2025']:
        pr = [v for v in C['project'][g].values() if v.get('proofs', 0) >= 20]
        chi = np.clip([v['chi_mean'] for v in pr], 0, lim)
        rho = np.clip([v['rho_mean'] for v in pr], 0, lim)
        big = g == 'mathlib'
        ax.scatter(chi, rho, s=7 if big else 18, color=COL[g], alpha=0.35 if big else 0.85,
                   edgecolors='white' if not big else 'none', linewidths=0.6,
                   label=f'{NAME[g]} ({len(pr)})', zorder=1 if big else 3)
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_aspect('equal')
    ax.set_xlabel(r'compressibility $\chi$ (mean bits per proof)')
    ax.set_ylabel(r'redundancy $\rho$ (mean bits per proof)')
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1.0), handletextpad=0.2)
    save(fig, 'chi_rho.pdf')


def layout_controls():
    """Divergence over null on the full data and on the three layout-controlled subsets."""
    sub = [('analysis_merged', 'all theorems'), ('analysis_proofs', 'proofs only'),
           ('analysis_rho0', r'optimal layout ($\rho=0$)'), ('analysis_nocut', 'no cuts')]
    rows = []
    for d, lab in sub:
        R = json.load(open(os.path.join(EG, 'out_final', d, 'results.json')))
        rows.append((lab, R['kl_bits']['openai'] / R['null']['total_median'],
                     R['kl_bits']['human'] / R['null_human']['total_median']))
    fig, ax = plt.subplots(figsize=(5.0, 1.9))
    y = np.arange(len(rows))[::-1]
    ax.axvline(1, color=INK2, lw=0.8)
    ax.text(1.05, y[0] + 0.45, 'null', color=INK2, fontsize=8)
    for yi, (lab, o, h) in zip(y, rows):
        ax.plot([h, o], [yi, yi], color=GRID, lw=2, zorder=1)
        ax.scatter([o], [yi], s=34, color=COL['openai'], zorder=3, edgecolors='white', linewidths=0.8)
        ax.scatter([h], [yi], s=34, color=COL['human'], zorder=3, edgecolors='white', linewidths=0.8)
        ax.text(o + 0.15, yi, f'{o:.1f}', va='center', fontsize=8, color=INK)
        ax.text(h - 0.15, yi, f'{h:.1f}', va='center', ha='right', fontsize=8, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_xlim(0, 7)
    ax.set_ylim(-0.6, len(rows) - 0.2)
    ax.set_xlabel('divergence from mathlib / size-matched null')
    ax.grid(axis='y', visible=False)
    ax.scatter([], [], s=34, color=COL['openai'], label='OpenAI')
    ax.scatter([], [], s=34, color=COL['human'], label='human research')
    ax.legend(loc='lower right', ncol=2, bbox_to_anchor=(1.0, 1.0))
    save(fig, 'layout_controls.pdf')


def realized_by_size():
    """Realized share within bins of cut-free size."""
    T = json.load(open(os.path.join(EG, 'out_terms', 'terms_results.json')))
    rb = T['realized_by_size']
    labels = ['10–29', '30–99', '100–299', '300–999', '1000+']
    fig, ax = plt.subplots(figsize=(5.0, 2.6))
    x = np.arange(len(labels))
    for g in ['mathlib', 'human', 'openai', 'spherepacking']:
        cells = rb['corpora'][g]
        ys = [c['realized'] * 100 if c and c['n'] >= 30 else np.nan for c in cells]
        ax.plot(x, ys, color=COL[g], lw=2, marker='o', ms=5, mec='white', mew=0.8, label=NAME[g])
        last = max(i for i, v in enumerate(ys) if not np.isnan(v))
        nudge = {'mathlib': 3, 'human': -3}.get(g, 0)
        ax.text(last + 0.12, ys[last] + nudge, NAME[g], va='center', fontsize=8, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlim(-0.2, len(labels) - 0.2)
    ax.set_ylim(0, 85)
    ax.set_xlabel('cut-free size (nodes)')
    ax.set_ylabel('realized share (%)')
    ax.grid(axis='x', visible=False)
    ax.legend(loc='lower left', bbox_to_anchor=(0, 1.0), ncol=4, handlelength=1.5)
    save(fig, 'realized_by_size.pdf')


def rank_panels():
    """mathlib, by the highest unfolded rank among a proof's shared cuts."""
    L = json.load(open(os.path.join(EG, 'out_terms', 'terms_results.json')))['corpora']['mathlib']['ladder_u']
    labels = ['none', '0', '1', '2', '3+']
    cells = [L[k] for k in ('-1', '0', '1', '2', '3')]
    dag = [c['chi_ub'] for c in cells]
    redex = [100 * c['residP'] for c in cells]
    fig, axs = plt.subplots(1, 2, figsize=(5.6, 2.1))
    x = np.arange(len(labels))
    for ax, v, yl, fmt in [(axs[0], dag, r'$\chi_{\mathrm{DAG}}$ (mean bits)', '{:.2f}'),
                           (axs[1], redex, 'created redexes (%)', '{:.0f}')]:
        ax.bar(x, v, width=0.6, color=COL['mathlib'])
        for xi, vi in zip(x, v):
            ax.text(xi, vi, fmt.format(vi), ha='center', va='bottom', fontsize=7.5, color=INK)
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_xlabel('highest rank of a shared cut')
        ax.set_ylabel(yl)
        ax.grid(axis='x', visible=False)
        ax.margins(y=0.15)
    fig.tight_layout(w_pad=2)
    save(fig, 'rank.pdf')


if __name__ == '__main__':
    text_energy()
    spectrum()
    chi_rho()
    layout_controls()
    realized_by_size()
    rank_panels()
