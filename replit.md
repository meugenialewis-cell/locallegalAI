# Local Legal AI Agent

A privacy-first legal workstation prototype for isolated matters, cited document retrieval, approval-gated tools, and local model configuration.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the shared API server
- `pnpm --filter @workspace/legal-agent run dev` — run the web interface
- `pnpm run typecheck` — full workspace typecheck
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas after OpenAPI changes
- `pnpm --filter @workspace/db run push` — apply development schema changes

## Stack

- pnpm workspaces, TypeScript, React, Vite, Express
- PostgreSQL + Drizzle for prototype persistence
- OpenAPI + Orval for shared API contracts
- TanStack Query for client data and mutations

## Where things live

- `artifacts/legal-agent/` — legal workstation web interface
- `artifacts/api-server/src/routes/legal-agent.ts` — legal agent API behavior
- `lib/api-spec/openapi.yaml` — source of truth for the product API
- `lib/db/src/schema/legal-agent.ts` — matters, documents, approvals, audit, and settings schema

## Product

- Dashboard with matter, document, approval, and safety posture summaries
- Matter workspaces with citation-bearing retrieval previews
- Tool proposal review with explicit approve/deny decisions
- Tamper-evident audit event chain
- Local runtime and model settings tailored to an Apple M5 Max with 128 GB unified memory

## Gotchas

- The Replit app is a functional prototype using demo data; it must not claim that the hosted preview itself is running locally on the user's Mac.
- The configured local model endpoint is intentionally disconnected in this environment.
- Computer use remains disabled until the macOS runtime has a real approval, isolation, and audit boundary.