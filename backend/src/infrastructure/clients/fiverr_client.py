# fiverr_client.py — REMOVED in v3.0
#
# SECURITY: There is zero Fiverr API connection in v3.0.
# No webhook endpoint exists. No HMAC signature validation.
# Salesperson manually pastes the customer message into the UI.
#
# Lead creation is handled via POST /api/v1/leads (manual entry).
# Profile tracking via src/domain/entities/fiverr_profile.py.

raise ImportError(
    "fiverr_client is no longer available in v3.0. "
    "Fiverr webhook integration has been removed by security mandate. "
    "Leads are created manually via POST /api/v1/leads."
)