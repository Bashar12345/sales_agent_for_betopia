"""OdooClient — implements IOdooPort via XML-RPC.

Odoo exposes a standard XML-RPC API at /xmlrpc/2/common and /xmlrpc/2/object.
This client is a thin wrapper; the full chatbot integration will be added later.
"""

import xmlrpc.client as xmlrpc
from functools import cached_property

import structlog

from src.application.ports.odoo_port import IOdooPort
from src.core.exceptions import OdooIntegrationError
from src.core.settings import settings
from src.domain.entities.lead import Lead
from src.domain.entities.quotation import Quotation

log = structlog.get_logger()


class OdooClient(IOdooPort):
    @cached_property
    def _uid(self) -> int:
        """Authenticate once and cache the user ID."""
        try:
            common = xmlrpc.ServerProxy(f"{settings.ODOO_URL}/xmlrpc/2/common")
            uid = common.authenticate(
                settings.ODOO_DB, settings.ODOO_USERNAME, settings.ODOO_API_KEY, {}
            )
            if not uid:
                raise OdooIntegrationError("Odoo authentication failed — check credentials")
            return uid
        except Exception as exc:
            raise OdooIntegrationError(f"Cannot connect to Odoo: {exc}") from exc

    @cached_property
    def _models(self):  # type: ignore[return]
        return xmlrpc.ServerProxy(f"{settings.ODOO_URL}/xmlrpc/2/object")

    def _execute(self, model: str, method: str, *args, **kwargs):  # type: ignore[return]
        try:
            return self._models.execute_kw(
                settings.ODOO_DB, self._uid, settings.ODOO_API_KEY,
                model, method, list(args), kwargs,
            )
        except Exception as exc:
            raise OdooIntegrationError(f"Odoo call {model}.{method} failed: {exc}") from exc

    async def sync_lead(self, lead: Lead) -> int:
        existing = self._execute(
            "crm.lead", "search",
            [[["ref", "=", f"fiverr-{lead.fiverr_order_id}"]]],
        )
        values = {
            "name": lead.name,
            "email_from": lead.email or "",
            "description": lead.requirement_summary,
            "ref": f"fiverr-{lead.fiverr_order_id}",
            "expected_revenue": lead.budget or 0,
        }
        if existing:
            self._execute("crm.lead", "write", existing, values)
            return existing[0]
        return self._execute("crm.lead", "create", values)

    async def sync_quotation(self, quotation: Quotation, lead: Lead) -> int:
        order_lines = [
            (0, 0, {
                "name": item.description,
                "product_uom_qty": item.quantity,
                "price_unit": item.unit_price,
            })
            for item in quotation.line_items
        ]
        values = {
            "partner_id": 1,  # Will be mapped to real partner once Odoo contacts are synced
            "note": quotation.notes,
            "order_line": order_lines,
            "client_order_ref": f"fiverr-{lead.fiverr_order_id}",
        }
        return self._execute("sale.order", "create", values)

    async def get_connection_status(self) -> bool:
        try:
            _ = self._uid
            return True
        except OdooIntegrationError:
            return False
