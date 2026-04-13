# Prompts Ownership (Prompt-as-Code)

| Directory | Owner | Pipeline |
|---|---|---|
| `p1_suggestion/` | **Dev 2** | Suggestion ranking + tone validation prompts |
| `p2_extraction/` | **Dev 3** | Extraction, enrichment, budget estimator prompts |
| `p3_parsing/` | **Dev 1** | Data parsing + schema validation prompts |
| `shared/system_persona.yaml` | **Dev 2** | Shared persona — coordinate changes with all devs |
| `shared/output_schemas/` | **Dev 1** | JSON schemas for structured outputs — all devs consume |

> Changing a prompt requires: increment version → run `eval_suite.yaml` → A/B test before 100% rollout.
