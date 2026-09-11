# One image, many services: SERVICE selects what this container runs.
#   SERVICE=ui        -> Foreman web UI + orchestrator (needs REGISTRY_URL, GOOGLE_API_KEY)
#   SERVICE=registry  -> agent registry (needs DELEGATE_URLS)
#   SERVICE=delegate  -> one delegate agent (needs DELEGATE=<name>, PUBLIC_URL)
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1 PORT=8080
CMD ["sh", "-c", "case \"$SERVICE\" in registry) python -m registry.main ;; delegate) python -m delegates.serve \"$DELEGATE\" ;; *) python -m ui.app ;; esac"]
