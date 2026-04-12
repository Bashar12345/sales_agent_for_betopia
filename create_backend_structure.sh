#!/usr/bin/env bash
set -euo pipefail

mkdir -p backend/{src/{api/v1,core,domain/{entities,services,repositories},application/{use_cases,dto,ports},infrastructure/{db/{migrations,seeds},cache,queue,clients,config},workers},tests/{unit,integration,contract,e2e},scripts,config,deploy/{docker,systemd,k8s,nginx},docs/{adr,api,runbooks},observability/{prometheus,grafana,loki},data/{samples,fixtures},.github/workflows}

touch backend/{README.md,.env.example,.gitignore,pyproject.toml,Makefile,Dockerfile,docker-compose.server.yml} \
backend/src/{main.py,__init__.py} \
backend/src/core/{settings.py,logging.py,security.py,exceptions.py} \
backend/src/api/v1/{router.py,health.py} \
backend/src/domain/entities/.gitkeep \
backend/src/domain/services/.gitkeep \
backend/src/domain/repositories/.gitkeep \
backend/src/application/use_cases/.gitkeep \
backend/src/application/dto/.gitkeep \
backend/src/application/ports/.gitkeep \
backend/src/infrastructure/db/{base.py,session.py,migrations/.gitkeep,seeds/.gitkeep} \
backend/src/infrastructure/cache/.gitkeep \
backend/src/infrastructure/queue/.gitkeep \
backend/src/infrastructure/clients/.gitkeep \
backend/src/infrastructure/config/.gitkeep \
backend/src/workers/.gitkeep \
backend/tests/unit/.gitkeep backend/tests/integration/.gitkeep backend/tests/contract/.gitkeep backend/tests/e2e/.gitkeep \
backend/scripts/{bootstrap.sh,test.sh,lint.sh,format.sh,run_server.sh} \
backend/config/{dev.yaml,staging.yaml,prod.yaml} \
backend/deploy/docker/{app.Dockerfile,worker.Dockerfile} \
backend/deploy/systemd/{backend.service,worker.service} \
backend/deploy/k8s/{namespace.yaml,configmap.yaml,secret.example.yaml,deployment.yaml,service.yaml,hpa.yaml,ingress.yaml} \
backend/deploy/nginx/{backend.conf} \
backend/docs/adr/0001-record-architecture-decisions.md \
backend/observability/prometheus/prometheus.yml \
backend/observability/grafana/.gitkeep \
backend/observability/loki/.gitkeep \
backend/.github/workflows/{ci.yml,cd.yml}

chmod +x backend/scripts/*.sh
echo "Backend structure created at ./backend"
