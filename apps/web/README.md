# apps/web — OSCAR Job Copilot frontend

SvelteKit + TypeScript + Tailwind CSS (fixed stack, ADR-001). Milestone 0 ships
route stubs for the 7 V1 screens ([../../docs/01_PRD.md](../../docs/01_PRD.md) §7);
none of them call the API yet.

## Setup

```bash
npm install
npm run dev            # http://127.0.0.1:5173, proxies /api → :8000
```

## Commands

| Command | Purpose |
|---|---|
| `npm run dev` | Dev server with API proxy (vite.config.ts) |
| `npm run build` | Production build |
| `npm run check` | `svelte-kit sync` + `svelte-check` |

## Screens

| Route | Screen | Arrives |
|---|---|---|
| `/` | Dashboard | M5 |
| `/jobs` | Job Inbox | M1 |
| `/jobs/[id]` | Job Detail | M1 (raw JD) / M4 (timeline) |
| `/cv/[id]` | CV Review | M3 |
| `/career-profile` | Career Profile | M2 |
| `/analytics` | Analytics | M5 |
| `/settings` | Settings | M2/M3 |

No design system is used (NFR-001, [../../docs/01_PRD.md](../../docs/01_PRD.md) §9) — plain Tailwind utility classes, tables, and forms only.
