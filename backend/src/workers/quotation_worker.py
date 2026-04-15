# [OWNER: Dev 3 — P2 Requirements Agent]
"""Background task: generate .docx quotation file.

Triggered after a quotation is created via the API.
Writes the file path back to the DB when done.
"""

import asyncio
import uuid

import structlog

from src.infrastructure.clients.document_generator import DocumentGenerator
from src.infrastructure.db.session import AsyncSessionLocal
from src.infrastructure.db.repositories.quotation_repository_impl import QuotationRepositoryImpl
from src.infrastructure.db.repositories.lead_repository_impl import LeadRepositoryImpl
from src.workers.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(name="generate_quotation_doc", bind=True, max_retries=3)
def generate_quotation_doc(self, quotation_id: str, lead_name: str, agent_name: str) -> str:
    """Build the .docx file and update the quotation record with doc_path."""
    async def _run() -> str:
        async with AsyncSessionLocal() as session:
            repo = QuotationRepositoryImpl(session)
            quot = await repo.get_by_id(uuid.UUID(quotation_id))
            if not quot:
                log.error("worker.quotation_not_found", quotation_id=quotation_id)
                return ""

            generator = DocumentGenerator()
            doc_path = await generator.generate_quotation_doc(
                quotation=quot,
                lead_name=lead_name,
                agent_name=agent_name,
            )
            quot.doc_path = doc_path
            await repo.update(quot)
            await session.commit()
            log.info("worker.doc_generated", path=doc_path)
            return doc_path

    from src.infrastructure.db.session import engine as _engine  # noqa: PLC0415

    result: str = ""

    async def _run_and_dispose() -> None:
        nonlocal result
        try:
            result = await _run()
        finally:
            await _engine.dispose()

    try:
        asyncio.run(_run_and_dispose())
        return result
    except Exception as exc:
        log.error("worker.doc_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=30)
