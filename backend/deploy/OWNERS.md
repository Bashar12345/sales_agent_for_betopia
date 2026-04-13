# Deploy / Infra Ownership

| Directory / File | Owner | Notes |
|---|---|---|
| `docker-compose.yml` | **Zohra** | Local dev: postgres, redis, qdrant, nats |
| `postgres/init.sql` | **Zohra** | All 9 tables + indexes + partitioning |
| `qdrant/config.yaml` | **Zohra** | 3 collections config |
| `k8s/deployment.yaml` | **Bashar** | All service deployments |
| `k8s/hpa.yaml` | **Bashar** | HPA for all services |
| `k8s/keda-scaledobjects.yaml` | **Bashar** | KEDA queue-depth autoscaling |
| `k8s/ingress.yaml` | **Bashar** | Kong ingress rules |
| `docker/app.Dockerfile` | **Bashar** | FastAPI app image |
| `docker/worker.Dockerfile` | **Bashar** | Celery worker image |
| `.github/workflows/ci.yml` | **Bashar** | Lint + test + prompt eval on PR |
| `.github/workflows/cd.yml` | **Bashar** | Build + push + deploy on merge |
