# Agentic Lead Operations — research to approved CRM entry

**Business problem:** Teams copy lead information across research, outreach drafts and CRM systems without traceable review. **Target outcome:** Fewer manual handoffs, with the final CRM write gated by a person.

## Architecture
A deterministic tool-driven workflow with persisted checkpoints: `created → research → qualify → draft → awaiting_approval → CRM`, or `rejected`/`research_failed`. The state machine is deliberately inspectable instead of an unbounded autonomous agent. `research_tool`, `qualify_tool`, `draft_tool`, and CRM write are explicit tool interfaces. Local research catalog is **mock data**, and no email or LinkedIn message is sent.

## Run
```bash
pip install -r requirements.txt
uvicorn app:app --reload
pytest -q
curl -X POST localhost:8000/workflows -H 'Content-Type: application/json' -d '{"company":"Acme Energy","contact":"Sam","email":"sam@example.com","industry":"energy"}'
# Copy returned id; inspect GET /workflows/{id}; POST /workflows/{id}/approval with {"approve":true}
```
API demo: `/docs`. Optional `OPENAI_API_KEY` enables custom drafting; the default uses a safe template. Request approval **before** any CRM side effect; repeated approval fails with HTTP 409 and the unique constraint prevents duplicate logs.

## Boundaries / next production steps
This is a runnable **local simulated CRM** backed by SQLite, not a real Salesforce/HubSpot integration. Replace research catalog with licensed, cited enrichment API; add tool retry/backoff, OAuth CRM adapter, draft editing screen, RBAC, encryption, and event/audit retention. Memory is persisted workflow state, not a multi-user long-term semantic memory. Do not represent fictional leads as real leads.

## Evaluation and pitch
Tests validate approval/rejection and one-write behavior. Report approvals per lead, successful CRM writes, operator minutes saved, tool-error rate, and research factuality on a labeled test set after you run a pilot. Record a demo showing a lead created, draft held, approval clicked, CRM entry displayed.
