# Domain Layer Ownership

## entities/

| File | Owner |
|---|---|
| `suggestion.py`, `message.py`, `conversation.py` | **Dev 2** |
| `requirements_doc.py`, `proposal.py`, `quotation.py`, `resource.py` | **Dev 3** |
| `lead.py`, `fiverr_profile.py`, `sales_agent.py` | **Dev 4** |

## services/

| File | Owner | Responsibility |
|---|---|---|
| `reply_service.py` | **Dev 2** | Filter + rank P1 suggestions (pure domain logic) |
| `quotation_service.py` | **Dev 3** | Gap detection + confidence scoring (pure domain logic) |

## repositories/ (interfaces only — implementations live in infrastructure/db/repositories/)

| File | Owner |
|---|---|
| `conversation_repository.py` | **Dev 2** |
| `quotation_repository.py`, `resource_repository.py` | **Dev 3** |
| `lead_repository.py` | **Dev 4** |
