# [OWNER: Dev 1 — Data Foundation (P3)]
"""Celery application factory.

Workers handle CPU/IO-heavy background tasks so the HTTP server
stays responsive for the ~1000 daily active users.

Current tasks:
  - generate_quotation_doc: build .docx after a quotation is created
  - index_conversation:     embed a closed conversation into ChromaDB
"""

from celery import Celery

from src.core.settings import settings

celery_app = Celery(
    "sales_agent",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "src.workers.quotation_worker",
        "src.workers.indexing_worker",
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
