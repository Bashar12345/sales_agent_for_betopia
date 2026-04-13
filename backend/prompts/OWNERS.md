# Prompts Ownership (Prompt-as-Code)

| Directory | Owner | Pipeline |
|---|---|---|
| `p1_suggestion/` | **Niloy** | Suggestion ranking + tone validation prompts |
| `p2_extraction/` | **Akash** | Extraction, enrichment, budget estimator prompts |
| `p3_parsing/` | **Zohra** | Data parsing + schema validation prompts |
| `shared/system_persona.yaml` | **Niloy** | Shared persona — coordinate changes with all devs |
| `shared/output_schemas/` | **Zohra** | JSON schemas for structured outputs — all devs consume |

> Changing a prompt requires: increment version → run `eval_suite.yaml` → A/B test before 100% rollout.
