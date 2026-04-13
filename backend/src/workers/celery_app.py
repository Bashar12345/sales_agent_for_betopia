# [OWNER: Dev 1 — Data Foundation (P3)]
"""Celery application factory.

Workers handle CPU/IO-heavy background tasks so the HTTP server
stays responsive for the ~2000 concurrent users.

Current tasks:
  - generate_p1_suggestions: full P1 pipeline (intent → embed → Qdrant → LLM → cache)
  - generate_quotation_doc:  build .docx after a quotation is created
  - index_conversation:      embed a closed conversation into Qdrant (P3)
"""

from celery import Celery

from src.core.settings import settings

celery_app = Celery(
    "sales_agent",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "src.workers.p1_suggestion_worker",   # P1: generate 5 suggestions
        "src.workers.quotation_worker",        # P2: .docx quotation generation
        "src.workers.indexing_worker",         # P3: embed conversations into Qdrant
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,   # fair dispatch for slow LLM tasks
)
