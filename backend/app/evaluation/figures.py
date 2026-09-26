"""Report figures (PNG). Palette and mark rules follow the project's dataviz conventions."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from app.evaluation.experiments import FEATURE_SETS, PERSONAS, THRESHOLDS, WINDOWS  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
BLUES = LinearSegmentedColormap.from_list("seq", ["#f4f8fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
PERSONA_LABEL = {"coder": "Coder", "leader": "Leader", "researcher": "Researcher", "all_rounder": "All-rounder", "fading": "Fading"}
TREND_ORDER = ["emerging", "improving", "stable", "declining", "inactive"]

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "text.color": INK,
        "axes.labelcolor": INK2,
        "axes.edgecolor": GRID,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "xtick.color": INK2,
        "ytick.color": INK2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "legend.frameon": False,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
    }
)


def _save(fig, out: Path, name: str) -> str:
    fig.savefig(out / name)
    plt.close(fig)
    return name


def trajectories(desc: dict, out: Path) -> str:
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    x = np.arange(-24, 1)
    ends = []
    for i, p in enumerate(PERSONAS):
        tr = desc["trajectories"][p]
        y = tr["mean"]
        ax.plot(x, y, color=SERIES[i], lw=2, label=f"{PERSONA_LABEL[p]} ({tr['competency'].replace('_', ' ')})")
        ends.append([y[-1], PERSONA_LABEL[p]])
    ends.sort()
    for a, b in zip(ends, ends[1:]):  # keep end labels at least 5 points apart
        b[0] = max(b[0], a[0] + 5)
    for y_end, label in ends:
        ax.text(0.4, y_end, label, va="center", color=INK2, fontsize=8)
    ax.set_xlim(-24, 4)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Months before evaluation date")
    ax.set_ylabel("Mean score")
    ax.set_title("Signature competency of each persona over 24 months")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", fontsize=7.5, ncol=2)
    return _save(fig, out, "fig1_persona_trajectories.png")


def confusion(default: dict, tuned: dict, out: Path, tuned_label: str) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.2), sharey=True)
    for ax, res, title in ((axes[0], default, "Default parameters"), (axes[1], tuned, f"Tuned ({tuned_label})")):
        m = np.array([[res["confusion"][p].get(t, 0) for t in TREND_ORDER] for p in PERSONAS], dtype=float)
        share = m / m.sum(1, keepdims=True)
        ax.imshow(share, cmap=BLUES, vmin=0, vmax=1, aspect="auto")
        for i in range(len(PERSONAS)):
            for j in range(len(TREND_ORDER)):
                if m[i, j]:
                    ax.text(j, i, int(m[i, j]), ha="center", va="center", fontsize=8, color="white" if share[i, j] > 0.55 else INK)
        ax.set_xticks(range(len(TREND_ORDER)), [t.capitalize() for t in TREND_ORDER], rotation=30, ha="right")
        ax.set_yticks(range(len(PERSONAS)), [PERSONA_LABEL[p] for p in PERSONAS])
        ax.grid(False)
        ax.set_title(f"{title}\nbalanced accuracy {res['balanced_accuracy']:.2f}", fontsize=9)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_xlabel("Predicted trend")
        ax.tick_params(axis="y", length=0)
    axes[0].set_ylabel("Persona (ground truth)")
    return _save(fig, out, "fig2_trend_confusion.png")


def sweep(sweep_res: dict, out: Path) -> str:
    best_hl = sweep_res["best"]["half_life"]
    grid = sweep_res["grid_test"]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(8.6, 3.2), gridspec_kw={"width_ratios": [3, 2]})
    m = np.array([[grid[f"hl={best_hl:g}|w={w}|t={t:g}"] for t in THRESHOLDS] for w in WINDOWS])
    ax.imshow(m, cmap=BLUES, vmin=0.3, vmax=0.9, aspect="auto")
    for i in range(len(WINDOWS)):
        for j in range(len(THRESHOLDS)):
            ax.text(j, i, f"{m[i, j]:.2f}", ha="center", va="center", fontsize=8, color="white" if m[i, j] > 0.7 else INK)
    ax.set_xticks(range(len(THRESHOLDS)), [f"{t:g}" for t in THRESHOLDS])
    ax.set_yticks(range(len(WINDOWS)), [f"{w} mo" for w in WINDOWS])
    ax.set_xlabel("Slope threshold (points / month)")
    ax.set_ylabel("Trend window")
    ax.grid(False)
    ax.set_title(f"Balanced accuracy, held-out (half-life {best_hl:g} mo)", fontsize=9)

    hl = sweep_res["by_half_life_test"]
    labels = ["∞" if k == "inf" else f"{k} mo" for k in hl]
    ax2.bar(labels, list(hl.values()), color=SERIES[0], width=0.6)
    for i, v in enumerate(hl.values()):
        ax2.text(i, v + 0.01, f"{v:.2f}", ha="center", va="bottom", fontsize=8, color=INK2)
    ax2.set_ylim(0, 1)
    ax2.set_xlabel("Decay half-life")
    ax2.set_title("Best balanced accuracy by half-life", fontsize=9)
    ax2.grid(axis="x", visible=False)
    return _save(fig, out, "fig3_parameter_sweep.png")


def clustering(res: dict, out: Path) -> str:
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(9.2, 3.8), gridspec_kw={"width_ratios": [3, 2]})
    kinds = list(FEATURE_SETS)
    y = np.arange(len(kinds))
    ari = [res["feature_sets"][k]["ari"] for k in kinds]
    nmi = [res["feature_sets"][k]["nmi"] for k in kinds]
    ax.barh(y - 0.19, ari, height=0.36, color=SERIES[0], label="ARI")
    ax.barh(y + 0.19, nmi, height=0.36, color=SERIES[1], label="NMI")
    for yy, a, n in zip(y, ari, nmi, strict=True):
        ax.text(a + 0.01, yy - 0.19, f"{a:.2f}", va="center", fontsize=7.5, color=INK2)
        ax.text(n + 0.01, yy + 0.19, f"{n:.2f}", va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(y, [FEATURE_SETS[k] for k in kinds])
    ax.invert_yaxis()
    ax.set_xlim(0, 1.1)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2)
    ax.set_title(f"k-means (k={res['k']}) agreement with personas", fontsize=9)

    ks = list(res["silhouette_by_k"])
    ax2.plot([int(k) for k in ks], list(res["silhouette_by_k"].values()), color=SERIES[0], lw=2, marker="o", ms=4)
    ax2.set_xlabel("k")
    ax2.set_ylabel("Silhouette")
    ax2.set_ylim(0, max(0.5, max(res["silhouette_by_k"].values()) + 0.05))
    ax2.set_title(f"Silhouette by k ({FEATURE_SETS[res['detail_features']].split(' (')[0].lower()})", fontsize=9)
    return _save(fig, out, "fig4_clustering.png")


def sensitivity(res: dict, out: Path) -> str:
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    levels = list(res["levels"])
    x = [float(level) * 100 for level in levels]
    metrics = {
        "spearman": "Score rank correlation (Spearman)",
        "top1": "Same strongest competency",
        "trend_agreement": "Same trend label",
        "balanced_accuracy": "Persona trend recovery (bal. acc.)",
    }
    for i, (m, label) in enumerate(metrics.items()):
        mean = [res["levels"][lv][m]["mean"] for lv in levels]
        lo = [res["levels"][lv][m]["min"] for lv in levels]
        hi = [res["levels"][lv][m]["max"] for lv in levels]
        ax.fill_between(x, lo, hi, color=SERIES[i], alpha=0.12, lw=0)
        ax.plot(x, mean, color=SERIES[i], lw=2, marker="o", ms=4, label=label)
    ax.set_xticks(x, [f"±{v:g}%" for v in x])
    ax.set_ylim(0.4, 1.02)
    ax.set_xlabel("Random perturbation of every weight")
    ax.set_title(f"Robustness to weight changes ({res['runs']} runs per level; band = min–max)")
    ax.legend(loc="lower left", fontsize=8)
    return _save(fig, out, "fig5_weight_sensitivity.png")
