"""Run all P5 experiments and write results.json, figures and REPORT.md.

    python -m app.evaluation.run --out ../docs/evaluation          # full run (~5 min)
    python -m app.evaluation.run --out /tmp/eval --quick            # smoke test
"""

import argparse
import statistics
import json
import math
import platform
import time
from dataclasses import replace
from pathlib import Path

from app.evaluation import experiments as ex
from app.evaluation import figures
from app.evaluation.data import EVAL_DATE, LABELS, build_dataset
from app.services import analytics
from app.services.analytics import TrendParams
from app.services.scoring import DEFAULT_PARAMS

TUNE_SEEDS = [1, 2, 3]
TEST_SEEDS = [4, 5]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../docs/evaluation")
    ap.add_argument("--learners", type=int, default=200)
    ap.add_argument("--quick", action="store_true", help="small datasets and few runs, for testing the pipeline")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    n = 40 if args.quick else args.learners
    started = time.perf_counter()

    def log(msg: str) -> None:
        print(f"[{time.perf_counter() - started:6.1f}s] {msg}", flush=True)

    log(f"building datasets: tune seeds {TUNE_SEEDS}, test seeds {TEST_SEEDS}, {n} learners each")
    tune = [build_dataset(s, n) for s in TUNE_SEEDS]
    test = [build_dataset(s, n) for s in TEST_SEEDS]

    results: dict = {
        "meta": {
            "evaluation_date": EVAL_DATE.isoformat(),
            "learners_per_dataset": n,
            "tune_seeds": TUNE_SEEDS,
            "test_seeds": TEST_SEEDS,
            "python": platform.python_version(),
            "defaults": {
                "half_life_months": DEFAULT_PARAMS.half_life_months,
                "window_months": analytics.DEFAULT_TREND.window_months,
                "slope_threshold": analytics.DEFAULT_TREND.slope_threshold,
            },
        }
    }
    log("E0 describe")
    results["dataset"] = ex.describe(test[0])

    log("E1/E2 trend sweep")
    results["sweep"] = ex.trend_sweep(tune, test)
    b = results["sweep"]["best"]
    tuned_params = replace(DEFAULT_PARAMS, half_life_months=b["half_life"])
    tuned_trend = TrendParams(window_months=b["window"], slope_threshold=b["threshold"])
    results["trend_default"] = ex.trend_detail(test, DEFAULT_PARAMS, analytics.DEFAULT_TREND)
    results["trend_tuned"] = ex.trend_detail(test, tuned_params, tuned_trend)

    log("E3 clustering")
    results["clustering"] = ex.clustering(test)

    log("E3b in-app grouping")
    results["grouping"] = ex.grouping_validation(test)

    log("E4 sensitivity")
    results["sensitivity"] = ex.sensitivity(test, runs=3 if args.quick else 20)

    log("E5 scalability")
    big = build_dataset(99, 100 if args.quick else 1000)
    results["scalability"] = ex.scalability(big, sizes=(50, 100) if args.quick else (200, 500, 1000))

    log("figures")
    tuned_label = f"window {b['window']} mo, threshold {b['threshold']:g}, half-life {b['half_life']:g} mo"
    results["figures"] = [
        figures.trajectories(results["dataset"], out),
        figures.confusion(results["trend_default"], results["trend_tuned"], out, tuned_label),
        figures.sweep(results["sweep"], out),
        figures.clustering(results["clustering"], out),
        figures.sensitivity(results["sensitivity"], out),
        figures.grouping(results["grouping"], out),
    ]
    results["meta"]["runtime_s"] = round(time.perf_counter() - started, 1)
    (out / "results.json").write_text(json.dumps(results, indent=2, default=_json))
    (out / "REPORT.md").write_text(report(results), encoding="utf-8")
    log(f"done -> {out.resolve()}")


def _json(o):
    if isinstance(o, float) and math.isinf(o):
        return "inf"
    raise TypeError(type(o))


# ---------- report ----------
def findings(r: dict) -> list[str]:
    s, td, tt = r["sweep"], r["trend_default"], r["trend_tuned"]
    gr = r["grouping"]
    b, fs = s["best"], r["clustering"]["feature_sets"]
    hl = s["by_half_life_test"]
    lv = r["sensitivity"]["levels"]
    worst = lv[max(lv, key=float)]
    sc = r["scalability"]
    big = max((k for k, v in sc.items() if isinstance(v, dict)), key=int)
    drops = [P[p] for p in ex.PERSONAS if tt["recall"][p] < td["recall"][p] - 0.05]
    return [
        f"1. **Trend detection recovers the intended trajectories well above chance.** Held-out balanced accuracy is "
        f"{td['balanced_accuracy']:.2f} with the default parameters and {tt['balanced_accuracy']:.2f} after tuning "
        f"(window {b['window']} months, threshold {b['threshold']:g} points/month; chance ≈ 0.20)."
        + (f" Tuning lowers recall for {', '.join(drops)}, whose scores are still rising slowly after 24 months." if drops else ""),
        f"2. **Forgetting (decay) is essential.** Without decay the best balanced accuracy falls to {hl['inf']:.2f} "
        f"(vs {hl['12']:.2f} with a 12-month half-life): declining learners cannot be detected at all.",
        f"3. **The competency profile's *shape* identifies learner types; its *level* does not.** Clustering on raw "
        f"scores gives ARI {fs['competency_now']['ari']:.2f}, while the profile shape reaches {fs['competency_shape']['ari']:.2f}, close to "
        f"the activity-count baseline ({fs['activity_counts']['ari']:.2f}). Time-bucketed raw counts do best "
        f"({fs['activity_counts_by_half_year']['ari']:.2f}), as the personas are defined by timing patterns.",
        f"4. **In-app groups and their movement are meaningful.** The production grouping (K-Means, k = 5) reaches ARI "
        f"{gr['k5']['algorithms']['K-Means']['ari']:.2f} against the personas (Agglomerative "
        f"{gr['k5']['algorithms']['Agglomerative']['ari']:.2f}, DBSCAN {gr['k5']['algorithms']['DBSCAN']['ari']:.2f}); "
        f"{100 * gr['movement_by_persona'].get('researcher', 0):.0f}% of researchers change group over the year as their research "
        f"emerges, against {100 * statistics.fmean(v for p, v in gr['movement_by_persona'].items() if p != 'researcher'):.0f}% of other learners.",
        f"5. **Results are robust to the expert weights.** With every weight perturbed by up to ±{float(max(lv, key=float)) * 100:g}%, score "
        f"rankings keep a Spearman correlation of {worst['spearman']['min']:.2f} or more (Kendall's τ ≥ {worst['kendall']['min']:.2f}), {100 * worst['trend_agreement']['mean']:.0f}% of trend "
        f"labels are unchanged and persona recovery stays at {worst['balanced_accuracy']['mean']:.2f}. The single *strongest* competency is "
        f"the least stable output ({100 * worst['top1']['mean']:.0f}% unchanged) because of near-ties.",
        f"6. **It scales comfortably for a department.** Full insights for one learner take {sc['insights_ms_per_learner']} ms; the cohort "
        f"view for {big} learners needs {sc[big]['cohort_trends_s']:.1f} s of computation.",
    ]



P = {"coder": "Coder", "leader": "Leader", "researcher": "Researcher", "all_rounder": "All-rounder", "fading": "Fading"}


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def report(r: dict) -> str:
    m, d, s = r["meta"], r["dataset"], r["sweep"]
    td, tt = r["trend_default"], r["trend_tuned"]
    cl, se, sc = r["clustering"], r["sensitivity"], r["scalability"]
    gr = r["grouping"]
    best = s["best"]
    lines = [
        "# Evaluation of the Competency Evolution Framework",
        "",
        f"_Generated by `python -m app.evaluation.run` · evaluation date {m['evaluation_date']} · runtime {m.get('runtime_s', '?')} s._",
        "",
        "## Key findings",
        "",
        *findings(r),
        "",
        "## 1. Method",
        "",
        f"Learner data is synthetic: {m['learners_per_dataset']} learners per dataset, 24 months of activity, generated by the "
        "production generator (`app/services/synthetic.py`). Each learner follows one of five personas whose intended trajectory "
        "is known, which gives ground truth for evaluating the analytics. Parameters are **tuned on datasets with seeds "
        f"{', '.join(map(str, m['tune_seeds']))}** and **reported on held-out datasets with seeds {', '.join(map(str, m['test_seeds']))}**.",
        "",
        "| Persona | Learners | Activities / learner | Signature competency | Intended trend |",
        "|---|---:|---:|---|---|",
    ]
    for p in ex.PERSONAS:
        comp, expected = ex.SIGNATURE[p]
        lines.append(
            f"| {P[p]} | {d['personas'][p]} | {d['activities_per_learner'][p]} | {LABELS[comp]} | {' or '.join(sorted(e.capitalize() for e in expected))} |"
        )
    lines += [
        "",
        f"![Persona trajectories]({r['figures'][0]})",
        "",
        "## 2. Trend detection (E1, E2)",
        "",
        "A learner's trend label for their signature competency is compared with the persona's intended trend. Because "
        "persona sizes differ, the headline metric is **balanced accuracy** (mean of per-persona recall; chance ≈ 0.2).",
        "",
        "| Configuration | Tuning seeds | Held-out seeds |",
        "|---|---:|---:|",
        f"| Default (half-life {m['defaults']['half_life_months']:g} mo, window {m['defaults']['window_months']} mo, threshold {m['defaults']['slope_threshold']:g}) | {s['default']['tune']:.3f} | **{s['default']['test']:.3f}** |",
        f"| Best on tuning seeds (half-life {best['half_life']:g} mo, window {best['window']} mo, threshold {best['threshold']:g}) | {best['tune']:.3f} | **{best['test']:.3f}** |",
        "",
        "Per-persona recall on held-out data:",
        "",
        "| Persona | Default | Tuned |",
        "|---|---:|---:|",
    ]
    lines += [f"| {P[p]} | {pct(td['recall'][p])} | {pct(tt['recall'][p])} |" for p in ex.PERSONAS]
    lines += [
        f"| **Balanced accuracy** | **{td['balanced_accuracy']:.3f}** | **{tt['balanced_accuracy']:.3f}** |",
        f"| Accuracy | {td['accuracy']:.3f} | {tt['accuracy']:.3f} |",
        "",
        "**Design decision.** The deployed app keeps the default 6-month window and 1.0 points/month threshold. Longer "
        "windows score higher against the personas, whose trajectories are defined over two years, but a learner-facing "
        "label should react to the last few months of activity so that feedback is timely and actionable; the tuned "
        "setting also labels most all-rounders 'Improving'. The window and threshold are parameters "
        "(`TrendParams`), so an institution can choose the other side of this trade-off.",
        "",
        f"![Confusion matrices]({r['figures'][1]})",
        "",
        f"![Parameter sweep]({r['figures'][2]})",
        "",
        "Best held-out balanced accuracy for each decay half-life (∞ = no decay):",
        "",
        "| Half-life | Best balanced accuracy |",
        "|---|---:|",
    ]
    lines += [f"| {'∞' if k == 'inf' else k + ' months'} | {v:.3f} |" for k, v in s["by_half_life_test"].items()]
    lines += [
        "",
        "## 3. Clustering learners (E3)",
        "",
        f"k-means (k = {cl['k']}, standardised features) is compared with the persona labels using the Adjusted Rand Index "
        "(ARI, 0 = chance, 1 = perfect) and Normalised Mutual Information (NMI). Two baselines use raw activity counts "
        "without the competency model.",
        "",
        "| Features | ARI | NMI |",
        "|---|---:|---:|",
    ]
    lines += [f"| {v['label']} | {v['ari']:.3f} | {v['nmi']:.3f} |" for v in cl["feature_sets"].values()]
    lines += [
        "",
        f"Cluster membership per persona ({cl['feature_sets'][cl['detail_features']]['label'].lower()}, first held-out dataset):",
        "",
        "| Persona | " + " | ".join(f"C{c}" for c in range(cl["k"])) + " |",
        "|---|" + "---:|" * cl["k"],
    ]
    lines += [f"| {P[p]} | " + " | ".join(str(cl["contingency"].get(p, {}).get(str(c), 0)) for c in range(cl["k"])) + " |" for p in ex.PERSONAS]
    lines += [
        "",
        f"Silhouette is highest at k = {max(cl['silhouette_by_k'], key=lambda k: cl['silhouette_by_k'][k])} "
        f"({max(cl['silhouette_by_k'].values()):.2f}): without labels the data forms fewer natural groups than there are personas, "
        "mainly because coders and all-rounders overlap.",
        "",
        f"![Clustering]({r['figures'][3]})",
        "",
        "### 3b. In-app learner groups (production code)",
        "",
        "The Learner groups page (`app/services/clustering.py`) is run unchanged on the held-out datasets: features are profile "
        "shape + volume, K-Means is fitted on three periods pooled (12 and 6 months ago, now), and Agglomerative (Ward) and "
        "DBSCAN are compared on the current period.",
        "",
        "| Algorithm | ARI (k = 5) | NMI (k = 5) | ARI (auto k) | Silhouette (auto k) | Davies–Bouldin (auto k) | Unassigned (auto k) |",
        "|---|---:|---:|---:|---:|---:|---:|",
        *[
            f"| {name} | {gr['k5']['algorithms'][name]['ari']:.3f} | {gr['k5']['algorithms'][name]['nmi']:.3f} | "
            f"{gr['auto']['algorithms'][name]['ari']:.3f} | {gr['auto']['algorithms'][name]['silhouette']:.3f} | "
            f"{gr['auto']['algorithms'][name]['davies_bouldin']:.3f} | {100 * gr['auto']['algorithms'][name]['noise']:.0f}% |"
            for name in gr["k5"]["algorithms"]
        ],
        "",
        f"Silhouette chose k = {', '.join(map(str, gr['auto']['k']))} on the held-out datasets. One grouping takes "
        f"{gr['auto']['seconds']:.2f} s for {m['learners_per_dataset']} learners.",
        "",
        "Share of learners whose group changed between 12 months ago and now (k = 5), a check of the transition analysis:",
        "",
        "| Persona | Changed group |",
        "|---|---:|",
        *[f"| {P[p]} | {pct(v)} |" for p, v in gr["movement_by_persona"].items()],
        "",
        f"![In-app grouping]({r['figures'][5]})",
        "",
        "## 4. Sensitivity to the weight matrix (E4)",
        "",
        f"Every non-zero weight is multiplied by a random factor in [1 − x, 1 + x] ({se['runs']} runs per level, both held-out "
        "datasets). Scores are compared with the unperturbed model.",
        "",
        "| Perturbation | Spearman ρ | Kendall's τ | Same strongest competency | Same trend label | Persona recovery (bal. acc.) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for lv, v in se["levels"].items():
        lines.append(
            f"| ±{float(lv) * 100:g}% | {v['spearman']['mean']:.3f} (min {v['spearman']['min']:.3f}) | "
            f"{v['kendall']['mean']:.3f} (min {v['kendall']['min']:.3f}) | {pct(v['top1']['mean'])} | "
            f"{pct(v['trend_agreement']['mean'])} | {v['balanced_accuracy']['mean']:.3f} (min {v['balanced_accuracy']['min']:.3f}) |"
        )
    lines += [
        "",
        f"![Weight sensitivity]({r['figures'][4]})",
        "",
        "## 5. Scalability (E5)",
        "",
        f"Pure computation time on one CPU core (mean {sc['mean_activities']} activities per learner), excluding database access.",
        "",
        "| Learners | Current scores | Scores + 6-month trends (cohort view) |",
        "|---:|---:|---:|",
    ]
    lines += [f"| {k} | {v['current_scores_s']:.2f} s | {v['cohort_trends_s']:.2f} s |" for k, v in sc.items() if isinstance(v, dict)]
    lines += [
        "",
        f"A single learner's full insights (36-month series, trends, recommendations, timeline) take **{sc['insights_ms_per_learner']} ms**.",
        "",
        "## 6. Threats to validity",
        "",
        "- **Synthetic ground truth.** Personas encode the designer's assumptions about how competencies develop; results show "
        "the analytics recover *those* patterns, not that the patterns match real learners. A pilot with real learner data is needed.",
        "- **Circularity.** The generator and the scoring model share the activity-type vocabulary, so clustering on "
        "competency features is expected to perform reasonably; the raw-count baselines are included to show what the model adds.",
        "- **Label noise.** Activity counts per 6-month window are small (Poisson), so some learners genuinely deviate from "
        "their persona's intended trend within the window; perfect recovery is not attainable.",
        "- **All-rounder ground truth.** 'Stable' assumes their scores have plateaued, but with a 12-month half-life scores "
        "are still rising slowly after 24 months, which lowers measured recall for this persona.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
