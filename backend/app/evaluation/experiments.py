"""P5 experiments. Every function is deterministic given its datasets and seeds."""

import math
import random
import statistics
import time
from collections import Counter
from dataclasses import replace
from datetime import date

import numpy as np
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from app.evaluation.data import EVAL_DATE, KEYS, TYPE_KEYS, Learner
from app.models.seed import MAPPING_WEIGHTS
from app.services import analytics
from app.services.analytics import TrendParams, add_months
from app.services.scoring import DEFAULT_PARAMS, ScoringParams, compute_scores

Weights = dict[str, dict[str, float]]
PERSONAS = ["coder", "leader", "researcher", "all_rounder", "fading"]

# Ground truth: each persona's signature competency and the trend label(s) its generator implies.
SIGNATURE: dict[str, tuple[str, set[str]]] = {
    "coder": ("technical", {"improving"}),
    "leader": ("leadership", {"improving"}),
    "researcher": ("research", {"improving", "emerging"}),
    "all_rounder": ("collaboration", {"stable"}),
    "fading": ("technical", {"declining"}),
}


# ---------- helpers ----------
def score_series(
    learner: Learner, points: int, weights: Weights = MAPPING_WEIGHTS, params: ScoringParams = DEFAULT_PARAMS, today: date = EVAL_DATE
) -> dict[str, list[float]]:
    """Scores at today − (points−1) … today months, oldest first."""
    out: dict[str, list[float]] = {k: [] for k in KEYS}
    for m in range(points - 1, -1, -1):
        for k, s in compute_scores(list(learner.activities), weights, KEYS, add_months(today, -m), params).items():
            out[k].append(s.score)
    return out


def trend_labels(series: dict[str, list[float]], p: TrendParams) -> dict[str, str]:
    return {k: analytics.classify(v, p) for k, v in series.items()}


def recovery(data: list[Learner], labels: list[dict[str, str]]) -> dict:
    """Per-persona recall of the intended trend on the signature competency."""
    hits: Counter = Counter()
    totals: Counter = Counter()
    confusion = {p: Counter() for p in PERSONAS}
    for learner, lab in zip(data, labels, strict=True):
        comp, expected = SIGNATURE[learner.persona]
        predicted = lab[comp]
        confusion[learner.persona][predicted] += 1
        totals[learner.persona] += 1
        hits[learner.persona] += predicted in expected
    recall = {p: hits[p] / totals[p] for p in PERSONAS if totals[p]}
    return {
        "accuracy": sum(hits.values()) / sum(totals.values()),
        "balanced_accuracy": statistics.fmean(recall.values()),
        "recall": recall,
        "confusion": {p: dict(c) for p, c in confusion.items()},
        "n": dict(totals),
    }


# ---------- E0: dataset description ----------
def describe(data: list[Learner]) -> dict:
    per = {p: [len(learner.activities) for learner in data if learner.persona == p] for p in PERSONAS}
    trajectories = {}
    for p in PERSONAS:
        comp = SIGNATURE[p][0]
        members = [learner for learner in data if learner.persona == p]
        series = [score_series(learner, 25)[comp] for learner in members]
        trajectories[p] = {"competency": comp, "mean": [round(statistics.fmean(col), 2) for col in zip(*series, strict=True)]}
    return {
        "learners": len(data),
        "personas": {p: len(v) for p, v in per.items()},
        "activities_per_learner": {p: round(statistics.fmean(v), 1) if v else 0 for p, v in per.items()},
        "total_activities": sum(len(learner.activities) for learner in data),
        "trajectories": trajectories,
    }


# ---------- E1/E2: trend detection and parameter sweep ----------
WINDOWS = [3, 6, 9, 12]
THRESHOLDS = [0.5, 0.75, 1.0, 1.5, 2.0]
HALF_LIVES = [6.0, 12.0, 24.0, math.inf]


def trend_sweep(tune: list[list[Learner]], test: list[list[Learner]]) -> dict:
    """Grid over half-life × window × threshold. Select on tune seeds, report on held-out test seeds."""

    def evaluate(datasets: list[list[Learner]]) -> dict[tuple, float]:
        scores: dict[tuple, list[float]] = {}
        for data in datasets:
            for hl in HALF_LIVES:
                params = replace(DEFAULT_PARAMS, half_life_months=hl)
                full = [score_series(learner, max(WINDOWS) + 1, params=params) for learner in data]
                for w in WINDOWS:
                    for t in THRESHOLDS:
                        p = TrendParams(window_months=w, slope_threshold=t)
                        labels = [trend_labels({k: v[-(w + 1) :] for k, v in s.items()}, p) for s in full]
                        scores.setdefault((hl, w, t), []).append(recovery(data, labels)["balanced_accuracy"])
        return {cfg: statistics.fmean(v) for cfg, v in scores.items()}

    tune_scores = evaluate(tune)
    test_scores = evaluate(test)
    default = (DEFAULT_PARAMS.half_life_months, analytics.DEFAULT_TREND.window_months, analytics.DEFAULT_TREND.slope_threshold)
    # Highest tuning score; ties go to the configuration closest to the default.
    best = max(tune_scores, key=lambda c: (round(tune_scores[c], 4), -abs(c[1] - default[1]) - abs(c[2] - default[2])))
    key = lambda c: f"hl={c[0]:g}|w={c[1]}|t={c[2]:g}"  # noqa: E731
    return {
        "default": {"config": key(default), "tune": tune_scores[default], "test": test_scores[default]},
        "best": {"config": key(best), "half_life": best[0], "window": best[1], "threshold": best[2], "tune": tune_scores[best], "test": test_scores[best]},
        "grid_tune": {key(c): v for c, v in tune_scores.items()},
        "grid_test": {key(c): v for c, v in test_scores.items()},
        "by_half_life_test": {
            f"{hl:g}": max(v for c, v in test_scores.items() if c[0] == hl) for hl in HALF_LIVES
        },
    }


def trend_detail(test: list[list[Learner]], params: ScoringParams, trend: TrendParams) -> dict:
    """Recovery + confusion on held-out data for one configuration."""
    merged_data, merged_labels = [], []
    for data in test:
        for learner in data:
            merged_data.append(learner)
            merged_labels.append(trend_labels(score_series(learner, trend.window_months + 1, params=params), trend))
    return recovery(merged_data, merged_labels)


# ---------- E3: clustering ----------
def features(data: list[Learner], kind: str) -> np.ndarray:
    rows = []
    for learner in data:
        if kind == "competency_now":
            s = score_series(learner, 1)
            rows.append([s[k][-1] for k in KEYS])
        elif kind == "competency_trajectory":
            s = score_series(learner, 7)
            rows.append([s[k][-1] for k in KEYS] + [s[k][-1] - s[k][0] for k in KEYS])
        elif kind in ("competency_raw", "competency_shape"):
            raw = [v.raw for v in compute_scores(list(learner.activities), MAPPING_WEIGHTS, KEYS, EVAL_DATE).values()]
            if kind == "competency_raw":
                rows.append([math.log1p(r) for r in raw])
            else:  # share of total points per competency, plus overall volume
                total = sum(raw)
                rows.append([r / total if total else 0.0 for r in raw] + [math.log1p(total)])
        elif kind == "activity_counts":
            c = Counter(a.type_key for a in learner.activities)
            rows.append([c[t] for t in TYPE_KEYS])
        elif kind == "activity_counts_by_half_year":
            row = []
            for q in range(4):  # 6-month buckets, oldest first
                lo, hi = add_months(EVAL_DATE, -24 + 6 * q), add_months(EVAL_DATE, -18 + 6 * q)
                c = Counter(a.type_key for a in learner.activities if lo <= a.start_date < hi)
                row += [c[t] for t in TYPE_KEYS]
            rows.append(row)
        else:
            raise ValueError(kind)
    return np.asarray(rows, dtype=float)


FEATURE_SETS = {
    "competency_now": "Competency scores (8)",
    "competency_trajectory": "Scores + 6-month change (16)",
    "competency_raw": "Log raw points, before saturation (8)",
    "competency_shape": "Competency profile shape + volume (9)",
    "activity_counts": "Baseline: activity-type counts (12)",
    "activity_counts_by_half_year": "Baseline: counts per 6-month period (48)",
}


# The competency-based feature set reported in detail (contingency table, silhouette).
CONTINGENCY_FEATURES = "competency_shape"


def clustering(test: list[list[Learner]], k: int = 5, seed: int = 0) -> dict:
    results: dict[str, dict] = {}
    contingency = None
    for kind in FEATURE_SETS:
        ari, nmi = [], []
        for i, data in enumerate(test):
            x = StandardScaler().fit_transform(features(data, kind))
            pred = KMeans(n_clusters=k, n_init=20, random_state=seed).fit_predict(x)
            truth = [learner.persona for learner in data]
            ari.append(adjusted_rand_score(truth, pred))
            nmi.append(normalized_mutual_info_score(truth, pred))
            if kind == CONTINGENCY_FEATURES and i == 0:
                contingency = {p: Counter(int(c) for c, t in zip(pred, truth, strict=True) if t == p) for p in PERSONAS}
        results[kind] = {"label": FEATURE_SETS[kind], "ari": statistics.fmean(ari), "nmi": statistics.fmean(nmi)}

    x = StandardScaler().fit_transform(features(test[0], CONTINGENCY_FEATURES))
    silhouette = {
        kk: float(silhouette_score(x, KMeans(n_clusters=kk, n_init=20, random_state=seed).fit_predict(x))) for kk in range(2, 9)
    }
    return {
        "k": k,
        "detail_features": CONTINGENCY_FEATURES,
        "feature_sets": results,
        "silhouette_by_k": silhouette,
        "contingency": {p: {str(c): n for c, n in sorted(v.items())} for p, v in (contingency or {}).items()},
    }


# ---------- E4: weight sensitivity ----------
def perturb(weights: Weights, level: float, rng: random.Random) -> Weights:
    """Multiply every non-zero weight by U(1−level, 1+level), clipped to [0, 1]. Zeros stay zero."""
    return {t: {c: (min(1.0, w * (1 + rng.uniform(-level, level))) if w > 0 else 0.0) for c, w in ws.items()} for t, ws in weights.items()}


def sensitivity(test: list[list[Learner]], levels=(0.1, 0.2, 0.3), runs: int = 20, seed: int = 7) -> dict:
    rng = random.Random(seed)
    trend = analytics.DEFAULT_TREND
    points = trend.window_months + 1
    base = []
    for data in test:
        series = [score_series(learner, points) for learner in data]
        base.append((data, series, [trend_labels(s, trend) for s in series]))

    out = {}
    for level in levels:
        rows = []
        for _ in range(runs):
            w = perturb(MAPPING_WEIGHTS, level, rng)
            spearman, top1, agree, bacc = [], [], [], []
            for data, series, labels in base:
                pseries = [score_series(learner, points, weights=w) for learner in data]
                plabels = [trend_labels(s, trend) for s in pseries]
                now = np.array([[s[k][-1] for k in KEYS] for s in series])
                pnow = np.array([[s[k][-1] for k in KEYS] for s in pseries])
                spearman.append(statistics.fmean(float(spearmanr(now[:, j], pnow[:, j]).statistic) for j in range(len(KEYS))))
                top1.append(float(np.mean(now.argmax(1) == pnow.argmax(1))))
                agree.append(statistics.fmean(a[k] == b[k] for a, b in zip(labels, plabels, strict=True) for k in KEYS))
                bacc.append(recovery(data, plabels)["balanced_accuracy"])
            rows.append({k: statistics.fmean(v) for k, v in {"spearman": spearman, "top1": top1, "trend_agreement": agree, "balanced_accuracy": bacc}.items()})
        out[f"{level:g}"] = {
            m: {"mean": statistics.fmean(r[m] for r in rows), "min": min(r[m] for r in rows), "max": max(r[m] for r in rows)}
            for m in rows[0]
        }
    return {"runs": runs, "levels": out}


# ---------- E5: scalability ----------
def scalability(data: list[Learner], sizes=(200, 500, 1000)) -> dict:
    out = {}
    for n in sizes:
        subset = data[:n]
        t0 = time.perf_counter()
        for learner in subset:
            compute_scores(list(learner.activities), MAPPING_WEIGHTS, KEYS, EVAL_DATE)
        t1 = time.perf_counter()
        for learner in subset:  # what the cohort / learner list endpoints do
            analytics.trends(analytics.monthly_series(list(learner.activities), MAPPING_WEIGHTS, KEYS, EVAL_DATE, max_months=6))
        t2 = time.perf_counter()
        out[str(n)] = {"current_scores_s": round(t1 - t0, 3), "cohort_trends_s": round(t2 - t1, 3)}

    sample = data[:50]
    t0 = time.perf_counter()
    for learner in sample:  # what /me/insights does for one learner (excluding the cohort percentile)
        acts = list(learner.activities)
        series = analytics.monthly_series(acts, MAPPING_WEIGHTS, KEYS, EVAL_DATE)
        tr = analytics.trends(series)
        _, gaps = analytics.strengths_and_gaps({k: t.score for k, t in tr.items()})
        analytics.recommendations(acts, MAPPING_WEIGHTS, KEYS, {k: k for k in KEYS}, {}, tr, gaps, EVAL_DATE)
        analytics.timeline(acts, MAPPING_WEIGHTS, KEYS, EVAL_DATE)
    out["insights_ms_per_learner"] = round(1000 * (time.perf_counter() - t0) / len(sample), 1)
    out["mean_activities"] = round(statistics.fmean(len(learner.activities) for learner in data), 1)
    return out
