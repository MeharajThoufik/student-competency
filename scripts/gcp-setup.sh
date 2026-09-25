#!/usr/bin/env bash
# One-time GCP setup for P0.
# Usage: ./scripts/gcp-setup.sh <PROJECT_ID> <BILLING_ACCOUNT_ID> [BUDGET]
# BUDGET must be in the billing account currency, e.g. 100USD or 8000INR (default 100USD).
# Prereqs: gcloud installed and `gcloud auth login` done; project already created and linked to billing.
set -euo pipefail

PROJECT_ID=${1:?PROJECT_ID required}
BILLING_ACCOUNT=${2:?BILLING_ACCOUNT_ID required (see: gcloud billing accounts list)}
BUDGET=${3:-100USD}
REGION=asia-south1
REPO=competency
SA_NAME=github-deployer
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"

echo "==> Enabling APIs"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  firebase.googleapis.com \
  firebasehosting.googleapis.com \
  billingbudgets.googleapis.com

echo "==> Budget alerts at 50% and 100% of ${BUDGET}"
gcloud billing budgets create \
  --billing-account="$BILLING_ACCOUNT" \
  --display-name="competency-budget" \
  --budget-amount="$BUDGET" \
  --filter-projects="projects/${PROJECT_ID}" \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=1.0

echo "==> Artifact Registry repo"
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker --location="$REGION" \
  --description="Competency API images" || echo "repo exists"

echo "==> Deployer service account for GitHub Actions"
gcloud iam service-accounts create "$SA_NAME" --display-name="GitHub deployer" || echo "SA exists"
for ROLE in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser roles/firebasehosting.admin; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" --role="$ROLE" --condition=None --quiet >/dev/null
done

gcloud iam service-accounts keys create github-deployer-key.json --iam-account="$SA_EMAIL"

cat <<MSG

Done. Next steps:
  1. Add Firebase to the project:   firebase projects:addfirebase ${PROJECT_ID}
  2. Put ${PROJECT_ID} in .firebaserc
  3. GitHub repo -> Settings -> Secrets and variables -> Actions:
       Secret   GCP_SA_KEY     = contents of github-deployer-key.json
       Variable GCP_PROJECT_ID = ${PROJECT_ID}
  4. DELETE github-deployer-key.json locally after adding the secret (it is gitignored).
MSG
