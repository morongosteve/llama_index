# Skill: gen-agent-docs

Generate agent-friendly API documentation conforming to the llms.txt standard.
This skill scans the project's Next.js App Router API routes, infers request/response
schemas, and produces two outputs:
  1. `public/llms.txt`          — concise entry-point (index) document
  2. `app/llms-full.txt/route.ts` — complete reference served at /llms-full.txt

## When to use

Run `/gen-agent-docs` any time you add, rename, or remove an API route, or change a
request/response schema. Always run it before deploying.

## What this skill does — step by step

### Step 1 — Discover routes

Find every `route.ts` file under `app/api/`:

```bash
find app/api -name "route.ts" | sort
```

For each file, read it with the Read tool and note:
- The HTTP methods exported (GET, POST, PUT, PATCH, DELETE)
- The URL path (derived from the directory structure, with `[param]` → `:param`)
- Every field destructured from `req.json()` body (POST/PUT/PATCH) — these are required body params
- Every `p.get("...")` or `searchParams.get("...")` call — these are query params
- The shape of every `NextResponse.json(...)` call — infer the response schema
- Every `{ status: NNN }` passed to NextResponse.json — note possible HTTP status codes

### Step 2 — Discover the data model

Read `lib/db.ts`. Extract every exported `interface` or `type`. These become the
"Data Model" section of the docs.

### Step 3 — Infer base URL

Check for `process.env.NEXT_PUBLIC_BASE_URL` in `lib/db.ts` or `app/llms-full.txt/route.ts`.
Check `.env.local` or `.env.local.example` for a default. If none found, use
a relative path (empty string) as the base URL so docs work from any deployment.

### Step 4 — Quality checklist (evaluate before writing)

Before writing any output, verify your draft satisfies every item below:

- [ ] Every exported HTTP method from every route.ts is documented
- [ ] Every query parameter (from searchParams) is listed with its type
- [ ] Every required body field (from req.json() destructuring) is listed
- [ ] Response shape for 200/201 is shown for every endpoint
- [ ] Every non-200 status code (400, 404, 500) has a documented error shape
- [ ] The data model section matches the exported interfaces in lib/db.ts
- [ ] /llms.txt lists every endpoint as a Markdown link
- [ ] /llms-full.txt includes a "Usage Notes for Agents" section
- [ ] /llms-full.txt includes a pagination example if any list endpoint exists
- [ ] Both files have an H1 title and a blockquote description (llms.txt spec requirement)

If any checklist item fails, revisit Step 1–3 before writing.

### Step 5 — Write `public/llms.txt`

Overwrite `public/llms.txt` with this structure (Markdown, plain text):

```
# <Project Name>

> <One sentence: what the API does and what data it manages.>

<2–3 sentences of context: auth model, data format, base URL.>

## Endpoints

- [<endpoint label>](<base_url><path>): <METHOD> <path> — <one-line description>
... (one bullet per endpoint)

## Optional

- [Full docs](<base_url>/llms-full.txt): GET /llms-full.txt — complete agent-readable API reference
- [Health check](<base_url>/api/health): GET /api/health — liveness probe
```

Rules:
- Use the actual base URL, not a placeholder, unless none is configured
- One bullet per unique endpoint (collapse GET+POST on the same path to two bullets)
- Keep each bullet under 120 characters
- No code blocks in llms.txt — it must be pure Markdown prose + links

### Step 6 — Write `app/llms-full.txt/route.ts`

Overwrite the file with a GET handler that returns `text/plain`. The response body
must include every section below. Use the existing file as a template for the
TypeScript boilerplate; only replace the `DOCS` string constant.

Required sections (in order):
1. `# <Project Name> — Full Reference`
2. `> <tagline>` blockquote
3. `## Overview` — auth model, content-type, base URL
4. `## Data Model` — table of fields for every exported interface
5. One `### <METHOD> <path>` section per endpoint, each containing:
   - Purpose sentence
   - Query parameters table (if any)
   - Request body schema (if POST/PUT/PATCH)
   - Response 200/201 JSON shape (with field comments)
   - All non-200 response shapes
   - A concrete `curl` example
6. `## Error Format` — the common error envelope
7. `## HTTP Status Codes` — table of all codes used
8. `## Pagination Pattern` — if any list endpoint accepts limit/offset
9. `## Usage Notes for Agents` — 5–8 numbered tips specific to this API

### Step 7 — Verify

After writing both files, start the dev server and confirm:

```bash
npm run dev -- --port 3099 &
sleep 5
curl -s http://localhost:3099/llms.txt | head -5
curl -s http://localhost:3099/llms-full.txt | grep "^###" | head -20
curl -I http://localhost:3099/llms.txt | grep content-type
pkill -f "next dev"
```

All three checks must pass:
1. `llms.txt` must start with `# ` (H1 heading)
2. `llms-full.txt` must list a `###` heading for every endpoint you documented
3. Content-Type for `llms.txt` must be `text/plain`

If any check fails, correct the relevant file and re-run.

### Step 8 — Report

Print a summary table:

```
| Output                        | Status |
|-------------------------------|--------|
| public/llms.txt               | ✅ written (N endpoints) |
| app/llms-full.txt/route.ts    | ✅ written (N endpoints) |
| /llms.txt content-type check  | ✅ text/plain |
| Quality checklist             | ✅ all N items passed |
```

If anything failed, list it under "Issues to address" with a one-line fix hint.
