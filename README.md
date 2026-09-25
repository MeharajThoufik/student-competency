# Competency Evolution Framework

Cloud-Based Continuous Competency Evolution Framework for Learner Profiling and Intelligent Educational Analytics.
M.Tech Case Study (21CSC601T) · SRM IST · SDG 4.

See [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) for features, architecture and the phased build plan.

## Stack
- **Frontend:** React + TypeScript + Vite + Tailwind → Firebase Hosting
- **Backend:** FastAPI (Python 3.12) → Cloud Run
- **Database:** PostgreSQL (local: docker-compose on port 5433, cloud: Cloud SQL)
- **Auth:** Firebase Auth (email/password + Google); the API verifies Firebase ID tokens
- **Evidence files:** local `backend/uploads/` in dev, private Cloud Storage bucket in production

## Run locally

**Option A: Docker (API + Postgres)**
```bash
docker compose up --build                    # API on http://localhost:8000, Postgres on 5433
cd frontend && npm install && npm run dev    # UI on http://localhost:5173
```

**Option B: No Docker**
```bash
cd backend
python -m venv .venv
.venv/Scripts/activate           # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
cp .env.example .env             # points at the docker-compose Postgres on port 5433
docker compose up -d db          # or any Postgres 16
alembic upgrade head
uvicorn app.main:app --reload --port 8000

cd frontend && npm install && npm run dev
```

- UI: http://localhost:5173 (proxies `/api` to port 8000)
- API docs: http://localhost:8000/api/docs
- Tests: `cd backend && pytest` (SQLite by default; set `TEST_DATABASE_URL` to run on Postgres)
- New migration after changing models: `alembic revision --autogenerate -m "..."`

## Deploy (GCP + Firebase)
1. Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install) and Firebase CLI (`npm i -g firebase-tools`).
2. `gcloud auth login` and `firebase login`.
3. Create a GCP project, link billing, then run:
   `./scripts/gcp-setup.sh <PROJECT_ID> <BILLING_ACCOUNT_ID>`
4. Follow the printed steps (Firebase, `.firebaserc`, GitHub secret/variable).
5. Push to `main`. GitHub Actions tests, deploys the API to Cloud Run, and deploys the UI to Firebase Hosting.

## Layout
```
backend/       FastAPI app (all routes under /api)
frontend/      React + Vite SPA
docs/          Project plan and reports
scripts/       One-time cloud setup
.github/       CI/CD workflow
firebase.json  Hosting config + /api/** → Cloud Run rewrite
```
