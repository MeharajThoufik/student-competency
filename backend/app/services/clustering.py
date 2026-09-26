"""Learner grouping (P5 intelligence layer). Pure functions, no database access.

Features per learner and point in time: the *shape* of the competency profile (each competency's
share of the learner's raw points) plus overall volume (log of total raw points). The P5 evaluation
showed shape identifies learner types far better than score levels (ARI 0.77 vs 0.41).

    1. Features for every learner at each period (e.g. 12 and 6 months ago, and now).
    2. Standardise; choose k by silhouette (Davies–Bouldin and inertia/elbow reported alongside).
    3. K-Means fitted on all periods pooled, so a group means the same thing at every period.
    4. Compare K-Means with Agglomerative (Ward) and DBSCAN on the current period.
    5. PCA to 2-D for a scatter plot; name each group from its centroid.
    6. Transitions: each learner's group at consecutive periods (or "not active yet").
"""

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

import numpy as np
from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, davies_bouldin_score, normalized_mutual_info_score, silhouette_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from app.services.analytics import add_months
from app.services.scoring import DEFAULT_PARAMS, ActivityInput, ScoringParams, compute_scores

INACTIVE = -1  # state for learners without a meaningful profile at a period
MIN_VOLUME = 0.5  # total raw points below which a learner has no profile yet
MIN_LEARNERS = 6
PERIODS = (12, 6, 0)  # months before today, oldest first
LIFT = 1.15  # a competency "defines" a group when its share is ≥ 15% above the cohort average
DBSCAN_MIN_SAMPLES = 5
DBSCAN_EPS_PERCENTILE = 60  # eps = this percentile of each point's distance to its 5th neighbour


@dataclass(frozen=True)
class LearnerHistory:
    id: int
    activities: tuple[ActivityInput, ...]
    truth: str | None = None  # persona of synthetic learners (evaluation only)


@dataclass
class Profile:
    features: list[float]  # 8 shares + log volume
    scores: dict[str, float]
    volume: float


def profile(activities: list[ActivityInput], weights, keys: list[str], as_of: date, params: ScoringParams = DEFAULT_PARAMS) -> Profile:
    s = compute_scores(activities, weights, keys, as_of, params)
    raw = [s[k].raw for k in keys]
    total = sum(raw)
    shares = [r / total if total else 0.0 for r in raw]
    return Profile(shares + [math.log1p(total)], {k: round(s[k].score, 2) for k in keys}, total)


@dataclass
class KChoice:
    k: int
    silhouette: float
    davies_bouldin: float
    inertia: float


@dataclass
class AlgorithmResult:
    name: str
    n_clusters: int
    noise: float  # share of points DBSCAN leaves unassigned
    silhouette: float | None
    davies_bouldin: float | None
    ari: float | None = None
    nmi: float | None = None


@dataclass
class Group:
    id: int
    name: str
    description: str
    size: int  # current period
    defining: list[str]  # competencies with share lift ≥ LIFT, strongest first
    mean_scores: dict[str, float]  # members' mean current scores
    lift: dict[str, float]  # centroid share / cohort share


@dataclass
class Grouping:
    as_of: date
    period_dates: list[date]
    k: int
    k_selection: list[KChoice]
    algorithms: list[AlgorithmResult]
    groups: list[Group]
    assignments: dict[int, list[int]]  # learner id -> state per period (INACTIVE or group id)
    pca: dict[int, tuple[float, float]]  # learner id -> 2-D position (current period, active only)
    pca_explained: list[float]
    transitions: list[dict[tuple[int, int], int]]  # per consecutive period pair: (from, to) -> learners
    movement_rate: float | None  # share of learners active at first and last period whose group changed
    persona_agreement: dict | None = None
    notes: list[str] = field(default_factory=list)


class NotEnoughLearners(ValueError):
    pass


def _metrics(x: np.ndarray, labels: np.ndarray) -> tuple[float | None, float | None]:
    mask = labels >= 0
    if len(set(labels[mask])) < 2 or mask.sum() < 3:
        return None, None
    return float(silhouette_score(x[mask], labels[mask])), float(davies_bouldin_score(x[mask], labels[mask]))


def _name_groups(centers: np.ndarray, keys: list[str], labels: dict[str, str], cohort_share: np.ndarray, vol_mean: float, vol_std: float):
    names, defining_all, lifts = [], [], []
    for c in centers:
        shares, vol = c[: len(keys)], c[len(keys)]
        lift = np.divide(shares, cohort_share, out=np.zeros_like(shares), where=cohort_share > 0)
        order = [i for i in np.argsort(-lift) if lift[i] >= LIFT]
        defining = [keys[i] for i in order[:3]]
        focus = " & ".join(labels[k] for k in defining[:2]) + " focus" if defining else "Balanced profile"
        z = (vol - vol_mean) / vol_std if vol_std > 0 else 0.0
        activity = " · high activity" if z >= 0.75 else " · low activity" if z <= -0.75 else ""
        names.append(focus + activity)
        defining_all.append(defining)
        lifts.append({keys[i]: round(float(lift[i]), 2) for i in range(len(keys))})
    counts = Counter(names)
    seen: Counter = Counter()
    for i, n in enumerate(names):  # disambiguate duplicates
        if counts[n] > 1:
            seen[n] += 1
            names[i] = f"{n} ({seen[n]})"
    return names, defining_all, lifts


def group_learners(
    learners: list[LearnerHistory],
    weights,
    keys: list[str],
    labels: dict[str, str],
    today: date,
    k: int | None = None,
    periods: tuple[int, ...] = PERIODS,
    seed: int = 0,
) -> Grouping:
    period_dates = [add_months(today, -m) for m in periods]
    now = len(periods) - 1
    profiles = {lh.id: [profile(list(lh.activities), weights, keys, d) for d in period_dates] for lh in learners}

    points = [(lid, p) for lid, ps in profiles.items() for p in range(len(periods)) if ps[p].volume >= MIN_VOLUME]
    current_ids = [lid for lid, ps in profiles.items() if ps[now].volume >= MIN_VOLUME]
    if len(current_ids) < MIN_LEARNERS:
        raise NotEnoughLearners(f"At least {MIN_LEARNERS} learners with activities are needed to form groups (found {len(current_ids)}).")

    raw = np.array([profiles[lid][p].features for lid, p in points])
    scaler = StandardScaler().fit(raw)
    x = scaler.transform(raw)
    is_now = np.array([p == now for _, p in points])
    x_now = x[is_now]
    now_ids = [lid for lid, p in points if p == now]

    # Model selection on the pooled data
    distinct = len(np.unique(x.round(6), axis=0))
    if distinct < 2:
        raise NotEnoughLearners("All learners currently have the same profile, so there is nothing to group yet.")
    max_k = min(8, len(current_ids) - 1, distinct - 1) if distinct > 2 else 2
    choices = []
    for kk in range(2, max_k + 1):
        km = KMeans(n_clusters=kk, n_init=10, random_state=seed).fit(x)
        choices.append(KChoice(kk, float(silhouette_score(x, km.labels_)), float(davies_bouldin_score(x, km.labels_)), float(km.inertia_)))
    notes = []
    if k is None:
        k = max(choices, key=lambda c: c.silhouette).k
        notes.append(f"k = {k} chosen automatically (highest silhouette).")
    k = max(2, min(k, max_k))

    km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(x)
    pooled_labels = km.labels_
    km_now = pooled_labels[is_now]

    # Algorithm comparison (current period)
    truth = {lh.id: lh.truth for lh in learners if lh.truth}
    y_true = [truth.get(lid) for lid in now_ids]
    has_truth = all(y_true) and len(set(y_true)) > 1

    def result(name: str, lab: np.ndarray) -> AlgorithmResult:
        sil, db = _metrics(x_now, lab)
        clusters = len(set(lab[lab >= 0]))
        r = AlgorithmResult(name, clusters, round(float(np.mean(lab < 0)), 3), sil, db)
        if has_truth:
            r.ari = float(adjusted_rand_score(y_true, lab))
            r.nmi = float(normalized_mutual_info_score(y_true, lab))
        return r

    nn = NearestNeighbors(n_neighbors=DBSCAN_MIN_SAMPLES).fit(x_now)
    # Floor: identical profiles give a 0 distance, which DBSCAN rejects as eps.
    eps = max(float(np.percentile(nn.kneighbors(x_now)[0][:, -1], DBSCAN_EPS_PERCENTILE)), 1e-6)
    algorithms = [
        result("K-Means", km_now),
        result("Agglomerative (Ward)", AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(x_now)),
        result(f"DBSCAN (eps {eps:.2f}, min {DBSCAN_MIN_SAMPLES})", DBSCAN(eps=eps, min_samples=DBSCAN_MIN_SAMPLES).fit_predict(x_now)),
    ]

    # Names from centroids in original feature units
    centers = scaler.inverse_transform(km.cluster_centers_)
    cohort_share = raw[is_now][:, : len(keys)].mean(0)
    vol = raw[:, len(keys)]
    names, defining, lifts = _name_groups(centers, keys, labels, cohort_share, float(vol.mean()), float(vol.std()))

    state = {lid: [INACTIVE] * len(periods) for lid in profiles}
    for (lid, p), lab in zip(points, pooled_labels, strict=True):
        state[lid][p] = int(lab)

    groups = []
    for g in range(k):
        members = [lid for lid in now_ids if state[lid][now] == g]
        mean_scores = {c: round(float(np.mean([profiles[lid][now].scores[c] for lid in members])), 1) if members else 0.0 for c in keys}
        top = ", ".join(f"{labels[c]} ×{lifts[g][c]:.1f}" for c in defining[g]) or "no competency stands out"
        groups.append(
            Group(
                id=g,
                name=names[g],
                description=f"Share of points compared with the cohort: {top}. Mean total points {math.expm1(centers[g][len(keys)]):.1f}.",
                size=len(members),
                defining=defining[g],
                mean_scores=mean_scores,
                lift=lifts[g],
            )
        )

    pca = PCA(n_components=2, random_state=seed).fit(x)
    coords = pca.transform(x_now)
    transitions = []
    for a in range(len(periods) - 1):
        transitions.append(dict(Counter((state[lid][a], state[lid][a + 1]) for lid in profiles)))
    both = [lid for lid in profiles if state[lid][0] != INACTIVE and state[lid][now] != INACTIVE]
    movement = sum(state[lid][0] != state[lid][now] for lid in both) / len(both) if both else None

    agreement = None
    if has_truth:
        contingency: dict[str, Counter] = {}
        for lid, t in zip(now_ids, y_true, strict=True):
            contingency.setdefault(t, Counter())[names[state[lid][now]]] += 1
        agreement = {
            "ari": float(adjusted_rand_score(y_true, km_now)),
            "nmi": float(normalized_mutual_info_score(y_true, km_now)),
            "contingency": {t: dict(c) for t, c in contingency.items()},
        }

    return Grouping(
        as_of=today,
        period_dates=period_dates,
        k=k,
        k_selection=choices,
        algorithms=algorithms,
        groups=groups,
        assignments=state,
        pca={lid: (round(float(c[0]), 3), round(float(c[1]), 3)) for lid, c in zip(now_ids, coords, strict=True)},
        pca_explained=[round(float(v), 3) for v in pca.explained_variance_ratio_],
        transitions=transitions,
        movement_rate=movement,
        persona_agreement=agreement,
        notes=notes,
    )
