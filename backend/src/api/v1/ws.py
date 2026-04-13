# [OWNER: Dev 2 — P1 Conversation Engine]
"""WebSocket endpoint — real-time suggestion push.

GET /api/v1/ws/suggestions/{lead_id}?token=<jwt>

Flow:
  1. Validate JWT from query param (WebSocket can't send Bearer headers)
  2. Accept the connection — immediately send {"ready": false, "status": "waiting"}
  3. Poll Redis every 500 ms for cached suggestions (set by p1_suggestion_worker)
  4. When suggestions arrive: send {"ready": true, "suggestions": [...]} and close
  5. If no suggestions arrive within 60 s: send {"ready": false, "timeout": true}
     so the client knows to fall back to HTTP polling via GET /suggestions/{lead_id}

Why Redis polling instead of NATS subscribe:
  - NATSClient is a publish-only helper; adding per-connection subscriptions
    would require a separate persistent connection per WebSocket client
  - The P1 worker already caches to Redis (step 9 in p1_suggestion_worker.py)
  - 500 ms poll latency is imperceptible to the salesperson
  - Simpler code, no NATS subscription lifecycle management

Auth:
  JWT is passed as ?token=<access_token> query parameter because the
  WebSocket protocol does not support custom headers in browser clients.
  decode_token() from security.py handles RS256 verification.
"""

import asyncio
import uuid

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError

from src.core.security import decode_token
from src.infrastructure.clients.redis_cache_client import RedisCacheClient

log = structlog.get_logger()

router = APIRouter(prefix="/ws", tags=["p1-websocket"])

_POLL_INTERVAL_S = 0.5    # 500 ms between Redis checks
_MAX_WAIT_S = 60.0        # 60 s before sending a timeout nudge


@router.websocket("/suggestions/{lead_id}")
async def ws_suggestions(
    websocket: WebSocket,
    lead_id: uuid.UUID,
    token: str | None = None,
) -> None:
    """Stream P1 suggestions to the salesperson as soon as they are ready.

    Connect immediately after POST /input/message returns 202.
    The server pushes one message and then closes the connection:
      - On success: {"ready": true, "lead_id": "...", "suggestions": [...]}
      - On timeout: {"ready": false, "timeout": true}
    """
    # ── Auth: validate JWT from query param ───────────────────────────────────
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    try:
        agent_claims = decode_token(token)
    except JWTError as exc:
        log.warning("ws.auth_failed", lead_id=str(lead_id), error=str(exc))
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    await websocket.accept()
    agent_id = agent_claims.get("sub", "unknown")
    log.info("ws.connected", lead_id=str(lead_id), agent_id=agent_id)

    # ── Immediately confirm connection is live ────────────────────────────────
    try:
        await websocket.send_json(
            {"ready": False, "status": "waiting", "lead_id": str(lead_id)}
        )
    except WebSocketDisconnect:
        log.info("ws.client_disconnected_early", lead_id=str(lead_id))
        return

    # ── Poll Redis until suggestions are cached or timeout ────────────────────
    cache = RedisCacheClient()
    elapsed = 0.0
    try:
        while elapsed < _MAX_WAIT_S:
            await asyncio.sleep(_POLL_INTERVAL_S)
            elapsed += _POLL_INTERVAL_S

            try:
                suggestions = await cache.get_suggestions(str(lead_id), "latest")
            except Exception as exc:
                log.warning("ws.cache_read_failed", error=str(exc))
                suggestions = None

            if suggestions:
                await websocket.send_json(
                    {
                        "ready": True,
                        "lead_id": str(lead_id),
                        "suggestions": suggestions,
                    }
                )
                log.info(
                    "ws.suggestions_pushed",
                    lead_id=str(lead_id),
                    count=len(suggestions),
                    elapsed_s=round(elapsed, 1),
                )
                return  # success path — connection will be closed in finally

        # Timeout — tell client to fall back to HTTP polling
        await websocket.send_json(
            {
                "ready": False,
                "timeout": True,
                "fallback_url": f"/api/v1/suggestions/{lead_id}",
            }
        )
        log.info("ws.timeout", lead_id=str(lead_id), waited_s=_MAX_WAIT_S)

    except WebSocketDisconnect:
        log.info("ws.client_disconnected", lead_id=str(lead_id), elapsed_s=round(elapsed, 1))
    finally:
        await cache.close()
        try:
            await websocket.close()
        except Exception:
            pass
