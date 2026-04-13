# [OWNER: Bashar — Frontend, Auth & DevOps]
"""Odoo ERP integration endpoints.

Current scope: connection health check + manual lead/quotation sync.
The full chatbot bridge will be implemented in a future iteration.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import OdooIntegrationError
from src.infrastructure.clients.odoo_client import OdooClient
from src.infrastructure.db.repositories.lead_repository_impl import LeadRepositoryImpl
from src.infrastructure.db.repositories.quotation_repository_impl import QuotationRepositoryImpl
from src.infrastructure.db.session import get_db

router = APIRouter(prefix="/integrations/odoo", tags=["odoo"])


@router.get("/status")
async def odoo_status() -> dict:
    """Check if Odoo credentials are valid and the server is reachable."""
    client = OdooClient()
    try:
        connected = await client.get_connection_status()
    except OdooIntegrationError as exc:
        return {"connected": False, "error": str(exc)}
    return {"connected": connected}


@router.post("/sync/lead/{lead_id}")
async def sync_lead_to_odoo(
    lead_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict:
    """Push a lead to Odoo CRM as a crm.lead record."""
    lead = await LeadRepositoryImpl(db).get_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    try:
        odoo_id = await OdooClient().sync_lead(lead)
        return {"lead_id": str(lead_id), "odoo_crm_lead_id": odoo_id}
    except OdooIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("/sync/quotation/{quotation_id}")
async def sync_quotation_to_odoo(
    quotation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict:
    """Push a quotation to Odoo as a sale.order record."""
    quot = await QuotationRepositoryImpl(db).get_by_id(quotation_id)
    if not quot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quotation not found")
    lead = await LeadRepositoryImpl(db).get_by_id(quot.lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    try:
        odoo_id = await OdooClient().sync_quotation(quot, lead)
        return {"quotation_id": str(quotation_id), "odoo_sale_order_id": odoo_id}
    except OdooIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
