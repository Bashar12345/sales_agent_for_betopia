# Deploy / Infra Ownership

| Directory / File | Owner | Notes |
|---|---|---|
| `docker-compose.yml` | **Dev 1** | Local dev: postgres, redis, qdrant, nats |
| `postgres/init.sql` | **Dev 1** | All 9 tables + indexes + partitioning |
| `qdrant/config.yaml` | **Dev 1** | 3 collections config |
| `k8s/deployment.yaml` | **Dev 4** | All service deployments |
| `k8s/hpa.yaml` | **Dev 4** | HPA for all services |
| `k8s/keda-scaledobjects.yaml` | **Dev 4** | KEDA queue-depth autoscaling |
| `k8s/ingress.yaml` | **Dev 4** | Kong ingress rules |
| `docker/app.Dockerfile` | **Dev 4** | FastAPI app image |
| `docker/worker.Dockerfile` | **Dev 4** | Celery worker image |
| `.github/workflows/ci.yml` | **Dev 4** | Lint + test + prompt eval on PR |
| `.github/workflows/cd.yml` | **Dev 4** | Build + push + deploy on merge |
