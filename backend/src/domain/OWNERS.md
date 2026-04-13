# Domain Layer Ownership

## entities/

| File | Owner |
|---|---|
| `suggestion.py`, `message.py`, `conversation.py` | **Niloy** |
| `requirements_doc.py`, `proposal.py`, `quotation.py`, `resource.py` | **Asif** |
| `lead.py`, `fiverr_profile.py`, `sales_agent.py` | **Bashar** |

## services/

| File | Owner | Responsibility |
|---|---|---|
| `reply_service.py` | **Niloy** | Filter + rank P1 suggestions (pure domain logic) |
| `quotation_service.py` | **Asif** | Gap detection + confidence scoring (pure domain logic) |

## repositories/ (interfaces only — implementations live in infrastructure/db/repositories/)

| File | Owner |
|---|---|
| `conversation_repository.py` | **Niloy** |
| `quotation_repository.py`, `resource_repository.py` | **Asif** |
| `lead_repository.py` | **Bashar** |
