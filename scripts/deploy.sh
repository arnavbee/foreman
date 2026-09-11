#!/usr/bin/env bash
# Deploy the whole Foreman stack to Cloud Run: 5 delegates, the registry, the UI.
# Prereqs: gcloud auth login; gcloud config set project $PROJECT; billing enabled; GOOGLE_API_KEY exported.
set -euo pipefail
PROJECT=${PROJECT:-$(gcloud config get-value project)}; REGION=${REGION:-asia-southeast1}
cd "$(dirname "$0")/.."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project "$PROJECT"
IMG="gcr.io/$PROJECT/foreman:$(git rev-parse --short HEAD)"
gcloud builds submit --tag "$IMG" --project "$PROJECT" .
urls=""
for d in researcher analyst writer quickfix oracle; do
  svc="foreman-$d"
  gcloud run deploy "$svc" --image "$IMG" --region "$REGION" --allow-unauthenticated --min-instances 0 --max-instances 2 \
    --set-env-vars "SERVICE=delegate,DELEGATE=$d,GOOGLE_API_KEY=${GOOGLE_API_KEY:-}" --project "$PROJECT" --quiet
  url=$(gcloud run services describe "$svc" --region "$REGION" --format 'value(status.url)' --project "$PROJECT")
  gcloud run services update "$svc" --region "$REGION" --update-env-vars "PUBLIC_URL=$url" --project "$PROJECT" --quiet
  urls="${urls:+$urls,}$d=$url"
done
gcloud run deploy foreman-registry --image "$IMG" --region "$REGION" --allow-unauthenticated \
  --set-env-vars "SERVICE=registry,DELEGATE_URLS=$urls" --project "$PROJECT" --quiet
REG=$(gcloud run services describe foreman-registry --region "$REGION" --format 'value(status.url)' --project "$PROJECT")
gcloud run deploy foreman --image "$IMG" --region "$REGION" --allow-unauthenticated --timeout 900 \
  --set-env-vars "SERVICE=ui,REGISTRY_URL=$REG,GOOGLE_API_KEY=${GOOGLE_API_KEY:-}" --project "$PROJECT" --quiet
echo "Foreman UI: $(gcloud run services describe foreman --region "$REGION" --format 'value(status.url)' --project "$PROJECT")"
