# Project Plan — Cloud-Based Continuous Competency Evolution Framework

**Full title:** Cloud-Based Continuous Competency Evolution Framework for Learner Profiling and Intelligent Educational Analytics
**Course:** 21CSC601T – Case Studies · M.Tech Cloud Computing & Blockchain · SRM IST
**Student:** Srivatshava K (RA2512062015003)
**SDG:** 4 – Quality Education
**Timeline:** Sep 26 – Oct 31, 2026 (~5 weeks)

---

## 1. Problem & Goal

Learner achievements (projects, certifications, competitions, workshops, co-curriculars) are scattered, and there is no structured way to see how a learner's competencies **evolve over time**.

**Goal:** a cloud-based system that keeps one unified learner profile, maps learning activities to competencies, tracks how each competency changes over time, and uses analytics to surface strengths, gaps and learner patterns.

### Research Questions
1. How can a learner's skills, competencies, interests and achievements be represented in a unified, continuously evolving profile?
2. Which learner attributes should be considered to represent overall growth beyond academic records?
3. Can a cloud-based framework effectively capture, manage and visualize continuous competency evolution?
4. Can a dynamic competency profile improve self-awareness and support educational/career decisions?

> ⚠️ Fix needed in `One Page Abstract.pdf`: RQ4 is currently a duplicate of RQ3 (the PPTX has the correct RQ4). Page 9 of the PDF is blank.

---

## 2. Features

### 2.1 Public
- Landing page (project summary, SDG 4)
- Login / Sign-up (email + Google via Firebase Auth)
- Consent screen on first login

### 2.2 Learner Portal
| Feature | Description |
|---|---|
| Unified profile | Personal info, semester-wise academics, skills, interests, goals |
| Add activity | Project, certification, hackathon, workshop, internship, club, paper, achievement — with level and date |
| Evidence upload | Certificate PDF/image to Cloud Storage; status 🟡 Self-reported → 🔵 Evidence attached → 🟢 Verified |
| Competency dashboard | Radar of 8 competencies, then-vs-now overlay, per-competency line charts |
| Trend labels | ⬆ Improving · ➡ Stable · ⬇ Declining · ✨ Emerging |
| Strengths & gaps | Top/bottom competencies with "why this score" explanation |
| Recommendations | Suggested activity types to strengthen weak areas |
| Learning timeline | Chronological activities with competency contributions |
| Interest evolution | Chart of how interests shifted over time |
| PDF report | Downloadable competency report |

### 2.3 Educator Portal
- Cohort overview (class-average radar, competency distributions)
- Student drill-down (read-only learner dashboard)
- Evidence verification queue (approve / reject → rescore)
- Learner groups — clustering scatter plot with auto-named groups
- Cohort movement — Sankey of cluster transitions over time
- Declining / inactive learner alerts

### 2.4 Admin Portal
- User & role management
- Competency taxonomy editor
- Mapping-weight matrix editor
- Audit log
- Manual recompute trigger

### 2.5 Stretch (only if time allows)
- Blockchain anchoring of verified certificate hashes (Polygon Amoy testnet)
- Anonymous peer percentile comparison
- NLP / LLM skill extraction from project descriptions
- Email notifications

### 2.6 Out of scope (Future Work)
- Real LMS/SIS integration and institutional SSO
- Dedicated graph database
- Multi-cloud deployment
- Supervised performance prediction (no labelled real-world data available)

---

## 3. Competency Model

**8 dimensions:** Technical, Problem-Solving, Communication, Leadership, Collaboration, Creativity, Research, Continuous Learning.

### 3.1 Scoring engine
```
contrib(a, c) = W[type(a), c] × level(a) × conf(a) × e^(−λ·Δt)
score_c       = 100 × (1 − e^(−Σ_a contrib(a, c) / k))
```
| Term | Meaning |
|---|---|
| `W` | Activity-type × competency weight matrix (0–1), expert-defined, editable by admin |
| `level` | Participation = 1, winner = 2, national/international multipliers |
| `conf` | Self-reported 0.5 · Evidence attached 0.8 · Educator-verified 1.0 |
| `e^(−λ·Δt)` | Time decay (half-life ≈ 12 months) — unused skills fade |
| Saturation | Keeps score in 0–100 with diminishing returns |

### 3.2 Evolution tracking
- **Event sourcing:** every activity change writes an immutable `competency_snapshot`
- **Trend classification:** linear-regression slope over a sliding window
- **Emerging detection:** threshold crossing from near-zero
- (Stretch) change-point detection with `ruptures`

---

## 4. Intelligent Analytics

| Component | Technique |
|---|---|
| Learner clustering | K-Means; k by elbow + silhouette; Davies–Bouldin index |
| Algorithm comparison | K-Means vs Agglomerative vs DBSCAN |
| Visualization | PCA → 2-D scatter |
| Cluster naming | Dominant centroid dimensions |
| ⭐ Temporal cluster transitions | Monthly re-clustering → transition matrix (Markov) → Sankey |
| Interest drift | Cosine similarity / Jensen–Shannon divergence between periods |
| Recommendations | Rule-based gap filling via `W`; (stretch) kNN collaborative filtering |
| Robustness | Sensitivity analysis: ±20% weight perturbation → Kendall's τ rank stability |

**Honest scope:** weights are expert-defined, not learned; no supervised prediction is claimed.

---

## 5. Architecture (GCP)

```
 Browser (React SPA)
      │  HTTPS
      ▼
 Firebase Hosting (CDN) ──── /api/** rewrite ────▶ Cloud Run: FastAPI API
      ▲                                               │
      │ Firebase Auth (JWT, role claims)              ├──▶ Cloud SQL (PostgreSQL)
                                                      ├──▶ Cloud Storage (evidence, signed URLs)
                                                      └──▶ Pub/Sub ──▶ Cloud Run: Worker
                                                                        (rescore, clustering, PDF)
 Cloud Scheduler (nightly decay + re-cluster) ──▶ Worker
 Cross-cutting: IAM · Secret Manager · encryption at rest · Cloud Logging/Monitoring · SQL backups · audit_log
```

| Diagram layer | Implementation |
|---|---|
| Data layer | Cloud Storage (raw evidence) + validated rows in Postgres |
| Processing layer | Mapping engine, scoring engine, analytics worker |
| Storage layer | PostgreSQL (competency relations as tables — graph DB deferred) |
| Services layer | FastAPI modular monolith + Pub/Sub worker |
| User interfaces | Learner / Educator / Admin dashboards |

---

## 6. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript + Vite, Tailwind CSS, shadcn/ui, Recharts, TanStack Query |
| Backend | Python FastAPI, SQLAlchemy 2, Alembic, Pydantic |
| Analytics | pandas, NumPy, scikit-learn |
| Reports | WeasyPrint / ReportLab |
| Database | Cloud SQL for PostgreSQL 16 |
| Files | Cloud Storage |
| Auth | Firebase Auth |
| Async / scheduling | Pub/Sub, Cloud Scheduler |
| Hosting | Firebase Hosting (frontend), Cloud Run (API + worker) |
| Secrets / Observability | Secret Manager, Cloud Logging & Monitoring |
| IaC / CI-CD | Terraform, GitHub Actions |
| Testing | pytest, Locust (load) |
| Stretch | Solidity + Hardhat, web3.py (Polygon Amoy) |

### Cost control (GCP $300 / 90-day trial)
- Budget alerts at $50 and $100 on day one
- Develop locally with docker-compose Postgres; Cloud SQL (smallest tier) is the only always-on cost
- Fallback DB: Neon / Supabase free tier
- After evaluation: `terraform destroy` or keep only free-tier services

---

## 7. Data Model

```
users(id, firebase_uid, role, name, email, programme, batch, consent_given)
competencies(id, name, description)
activity_types(id, name)
mapping_weights(activity_type_id, competency_id, weight)
activities(id, learner_id, type_id, title, description, date, level,
           evidence_status, verified_by, metadata JSONB)
evidence_files(id, activity_id, gcs_key, sha256, chain_tx_hash NULL)
academic_records(id, learner_id, semester, course, grade, credits)
skills(id, learner_id, name, self_level)
interests(id, learner_id, tag, weight, recorded_at)
competency_snapshots(id, learner_id, taken_at, scores JSONB, trigger_event)
cluster_runs(id, run_at, algorithm, k, silhouette, params JSONB)
cluster_assignments(run_id, learner_id, label, x, y)
audit_log(id, actor_id, action, entity, entity_id, at)
```

---

## 8. Repository Layout

```
student_Competency/
├── docs/                  # plan, report, diagrams, original PDF/DOCX/PPTX
├── frontend/              # React + Vite
├── backend/
│   ├── app/
│   │   ├── api/           # routers: auth, profile, activities, competency, analytics, admin
│   │   ├── models/
│   │   ├── services/      # mapping, scoring, analytics, reports
│   │   └── workers/
│   ├── alembic/
│   └── tests/
├── data/synthetic/        # generator + seed data
├── infra/terraform/
├── loadtest/              # Locust scripts
├── contracts/             # (stretch) Solidity
├── firebase.json
└── docker-compose.yml
```

---

## 9. Build Plan — Evolutionary Phases

Each phase ends with a **working, deployed increment** at the live link.

```
P0 Skeleton → P1 Profile → P2 Scoring → P3 Evolution → P4 Educator → P5 Intelligence → P6 Cloud-native → P7 Evaluate
```

### P0 · Walking Skeleton — Sep 26–28 (3 days)
- Monorepo, docker-compose (API + Postgres), Vite app, FastAPI `/api/health`
- GCP project, budget alerts, Artifact Registry
- Cloud Run deploy + Firebase Hosting with `/api/**` rewrite
- GitHub Actions CI/CD

**Exit:** live URL shows landing page; `/api/health` returns OK.

### P1 · Identity & Unified Profile — Sep 29–Oct 3 (5 days)
- Firebase Auth + JWT verification in FastAPI + role claims
- Cloud SQL, SQLAlchemy models, Alembic migrations
- Profile, academics, skills, interests, Add Activity, activity list
- Evidence upload via signed URLs; consent screen; route guards

**Exit:** learner logs in, builds profile, uploads certificates.

### P2 · Competency Engine — Oct 4–8 (5 days)
- Competencies + seeded mapping-weight matrix
- Scoring service with pytest unit tests
- Snapshot on every activity change (event sourcing)
- Synthetic data generator: 200 learners × 24 months, 5 personas
- Dashboard v1: radar + score explanation

**Exit:** adding an activity visibly changes the radar; demo data loaded.

### P3 · Evolution & Insight — Oct 9–13 (5 days)
- Per-competency line charts, then-vs-now radar
- Trend classifier, strengths & gaps, recommendations
- Learning timeline, interest drift chart

**Exit:** persona learners show clear growth with trend badges.

### P4 · Educator & Trust Layer — Oct 14–17 (4 days)
- Verification queue → rescore
- Cohort overview, student drill-down, declining alerts
- Admin: users/roles, weight editor, audit log
- PDF report export

**Exit:** full learner → educator → admin flow with 3 demo accounts.

### P5 · Intelligence Layer — Oct 18–23 (6 days)
- K-Means + silhouette/elbow + Davies–Bouldin; Agglomerative & DBSCAN comparison
- PCA scatter, auto cluster naming
- Temporal cluster transitions → transition matrix + Sankey
- Sensitivity analysis (Kendall's τ)
- Validate trend/cluster detection against synthetic personas

**Exit:** educator sees learner groups & cohort movement; result tables ready.

### P6 · Cloud-Native Hardening — Oct 24–26 (3 days)
- Pub/Sub → worker for async rescoring
- Cloud Scheduler nightly jobs
- Secret Manager, monitoring dashboard + alert
- Terraform for all infrastructure
- Locust load test (100 / 500 / 1000 users)

**Exit:** deployed system matches architecture diagram; load-test graphs captured.

### P7 · Evaluate & Document — Oct 27–31 (5 days)
- User study (10–20 students, 2–3 teachers): SUS + pre/post self-awareness survey
- Final report, updated diagrams, demo video, paper draft, slides
- Tag `v1.0`

**Exit:** submission-ready.

### Cut Line (drop in this order if behind)
1. Blockchain, NLP extraction, change-point detection
2. DBSCAN / Agglomerative comparison (keep K-Means)
3. Terraform (keep scripted `gcloud` deploy)
4. Pub/Sub (keep synchronous rescoring)

**Never cut:** P0–P3, K-Means + silhouette, verification, evaluation.

---

## 10. Evaluation Plan

| RQ | Method | Evidence |
|---|---|---|
| RQ1 | Schema coverage of all input categories + worked example learner | Coverage table, profile screenshots |
| RQ2 | Ablation: remove one data source, measure profile change & cluster quality | Ablation table |
| RQ3 | Trend-detection accuracy on synthetic personas; load test; backup/availability demo | Accuracy %, p95 latency, throughput graphs |
| RQ4 | User study with students & teachers | SUS score, pre/post Likert results |

---

## 11. Guide Checkpoints

| Date | Demo |
|---|---|
| Oct 3 | Live profile + activity upload |
| Oct 10 | Scoring engine + radar + synthetic data |
| Oct 17 | Evolution charts + educator workflow |
| Oct 24 | Clustering + transition results |
| Oct 31 | Final demo + report |

---

## 12. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Limited real learner data | Synthetic personas with known trajectories; small voluntary user study |
| Subjective competencies hard to measure | Transparent weight matrix + sensitivity analysis + "why this score" explanations |
| Unreliable self-reported data | Evidence-confidence weighting + educator verification |
| GCP credit overrun | Budget alerts, local dev, Cloud SQL only from P1, teardown after evaluation |
| Time overrun | Evolutionary phases + cut line; always a deployable version |
| Privacy of learner data | Consent, RBAC, signed URLs, encryption at rest, audit log |

---

## 13. References
1. A. Asselman, M. Khaldi, S. Aammou, "Enhancing the Prediction of Student Performance Based on the Machine Learning XGBoost Algorithm," *Interactive Learning Environments*, 31(6), 3360–3379, 2023. DOI: 10.1080/10494820.2021.1928235
2. M. Vitti et al., "A Competency Map for Circular Economy Education," *Procedia Computer Science*, 253, 336–345, 2025. DOI: 10.1016/j.procs.2025.01.096
3. C. Romero, S. Ventura, "Educational Data Mining and Learning Analytics: An Updated Survey," *WIREs Data Mining and Knowledge Discovery*, 10(3), e1355, 2020. DOI: 10.1002/widm.1355
