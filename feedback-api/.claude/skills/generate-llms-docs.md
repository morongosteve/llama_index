# generate-llms-docs

Generate agent-friendly documentation for the Feedback API following the llms.txt standard.

## When to use

Invoke this skill when:
- API routes have been added or changed
- You need to regenerate the `/llms.txt` or `/llms-full.txt` endpoints
- You want to verify that the docs match the actual API implementation

## Instructions

### Step 1: Discover all API routes

Scan `src/app/api/` recursively for all `route.ts` files. For each file:
- Identify which HTTP methods are exported (GET, POST, PATCH, PUT, DELETE)
- Read the route handler code to extract: path parameters, query parameters, request body shape, response shape, status codes, and validation rules

### Step 2: Read the data model

Read `src/lib/db.ts` to extract:
- The `Feedback` TypeScript interface (field names, types, descriptions)
- All available filter/sort/pagination options from the `getAll` function
- The summary response shape from `getSummary`

### Step 3: Generate llms.txt (concise index)

Write `src/app/llms.txt/route.ts` with a plain-text response containing:
- A one-line description of the API
- A bullet list of every endpoint: path, method, and one-line purpose
- A link to `/llms-full.txt` for full docs

Format: Follow the llms.txt standard — Markdown in a plain-text response. Keep it under 30 lines.

### Step 4: Generate llms-full.txt (comprehensive)

Write `src/app/llms-full.txt/route.ts` with a plain-text response containing:

1. **Data Model section**: The full Feedback interface as a JSON example, a table of all fields with types and descriptions
2. **Endpoints section**: For each endpoint:
   - HTTP method and path
   - Description
   - Query parameters table (if any) with name, type, description
   - Request body example (if POST/PATCH)
   - Response example with actual JSON shape
   - Error responses
3. **Working curl examples** for every endpoint
4. **Error handling section**: Status code table

### Step 5: Quality checklist

Verify the generated docs against this checklist:
- [ ] Every route in `src/app/api/` is documented
- [ ] All query parameters from `getAll` filters are listed
- [ ] Request body validation rules match the route handler code
- [ ] Response JSON shapes match what the API actually returns
- [ ] All HTTP status codes used in route handlers are documented
- [ ] The data model fields match the `Feedback` TypeScript interface
- [ ] curl examples use valid JSON and correct paths
- [ ] `/llms.txt` links to `/llms-full.txt`
- [ ] Both endpoints return `Content-Type: text/plain`

### Step 6: Build verification

Run `npm run build` from the project root to confirm the generated route handlers compile without TypeScript errors.

## Output

The skill modifies two files:
- `src/app/llms.txt/route.ts`
- `src/app/llms-full.txt/route.ts`

Report which endpoints were documented and whether the quality checklist passed.
