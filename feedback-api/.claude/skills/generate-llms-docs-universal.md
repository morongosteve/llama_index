# Generate llms.txt and llms-full.txt -- Universal API Documentation Skill

Generate agent-friendly API documentation following the llms.txt standard for any API project. This skill auto-detects the framework, discovers all routes, extracts schemas, and produces both a concise index (`llms.txt`) and comprehensive reference (`llms-full.txt`).

Supported frameworks: Next.js App Router, Next.js Pages Router, Express.js, FastAPI (Python).

---

## Step 1: Detect the Framework

Read project manifest files to determine which framework is in use. Check them in this order and stop at the first match.

### 1a. Check for Node.js projects

Read `package.json` in the project root. Inspect the `dependencies` and `devDependencies` objects.

| Condition | Framework |
|---|---|
| `"next"` is a dependency | **Next.js** (proceed to step 1b to distinguish App Router vs Pages Router) |
| `"express"` is a dependency | **Express.js** |

### 1b. Distinguish Next.js router type

Check for the existence of directories in this order:

1. If `src/app/api/` or `app/api/` exists --> **Next.js App Router**
2. If `src/pages/api/` or `pages/api/` exists --> **Next.js Pages Router**
3. If both exist, treat as **Next.js App Router** (the newer pattern takes priority) but note that Pages Router routes also exist and document both.
4. If neither exists, still classify as Next.js but note that no API routes were found yet -- the user may need to create them.

### 1c. Check for Python projects

If no `package.json` exists or it contains neither `next` nor `express`:

1. Read `pyproject.toml` -- look for `fastapi` in `[project.dependencies]` or `[tool.poetry.dependencies]`.
2. Read `requirements.txt` -- look for a line starting with `fastapi`.
3. Scan `*.py` files in the project root and `app/` or `src/` for `from fastapi import` or `import fastapi`.

If found --> **FastAPI**.

### 1d. Fallback

If no framework is detected, report the finding to the user and ask which framework they use. Do not guess.

---

## Step 2: Discover Routes

Based on the detected framework, follow the corresponding subsection below.

### 2a. Next.js App Router

**Where to look:** Recursively scan `src/app/api/` and `app/api/` for files named `route.ts` or `route.js`.

**How to extract the URL path:** The filesystem path maps directly to the URL. Strip the prefix (`src/app` or `app`) and the filename (`route.ts`). For example:
- `src/app/api/users/route.ts` --> `/api/users`
- `src/app/api/users/[id]/route.ts` --> `/api/users/[id]`
- `app/api/posts/[slug]/comments/route.ts` --> `/api/posts/[slug]/comments`

**How to extract HTTP methods:** Read each `route.ts`/`route.js` file. Look for named exports that match HTTP method names:
```
export async function GET(request: Request) { ... }
export async function POST(request: Request) { ... }
export async function PUT(request: Request) { ... }
export async function PATCH(request: Request) { ... }
export async function DELETE(request: Request) { ... }
```
Each exported function name IS the HTTP method for that route.

**How to extract request details:**
- **Query parameters:** Look for `request.nextUrl.searchParams`, `new URL(request.url).searchParams`, or destructured `searchParams` from the second argument. Record each `.get("paramName")` or `.getAll("paramName")` call.
- **Dynamic path parameters:** The second argument to the handler is `{ params }`. Look for destructuring like `{ params: { id } }` or `params.id` usage. Also infer from the `[bracketed]` folder names in the path.
- **Request body:** Look for `await request.json()`, `await request.formData()`, `await request.text()`. Then trace what fields are destructured or accessed from the result. Look for TypeScript type annotations on the parsed body, Zod `.parse()` / `.safeParse()` calls, or explicit destructuring like `const { name, email } = await request.json()`.
- **Response shape:** Look for `NextResponse.json(...)`, `Response.json(...)`, or `new Response(...)`. Record the object structure passed to `.json()`. Note the status code from `{ status: 201 }` options or `NextResponse.json(data, { status: 404 })`.
- **Auth:** Look for imports from auth libraries (`next-auth`, `@clerk/nextjs`, `@supabase/ssr`, custom `auth` utils), calls like `getServerSession()`, `auth()`, `getToken()`, header reads like `request.headers.get("authorization")`, and early returns with 401/403 status.

### 2b. Next.js Pages Router

**Where to look:** Recursively scan `pages/api/` and `src/pages/api/` for `.ts` and `.js` files (excluding `_middleware.ts`).

**How to extract the URL path:** Map filesystem path to URL by stripping `pages` or `src/pages` prefix and the file extension:
- `pages/api/users.ts` --> `/api/users`
- `pages/api/users/[id].ts` --> `/api/users/[id]`
- `pages/api/users/index.ts` --> `/api/users`

**How to extract HTTP methods:** Pages Router uses a single default export handler. Look inside the function body for method branching:
```
if (req.method === 'POST') { ... }
switch (req.method) { case 'GET': ... case 'POST': ... }
```
Collect every HTTP method string compared against `req.method`.

**How to extract request details:**
- **Query parameters:** Look for `req.query.paramName` or destructuring from `req.query`.
- **Dynamic path parameters:** Also accessed via `req.query` -- the `[bracketed]` filename segments appear as query keys.
- **Request body:** Look for `req.body` access. Trace the fields read from it. Look for type annotations or validation.
- **Response shape:** Look for `res.status(200).json({...})`, `res.json({...})`, `res.send(...)`. Record object shapes and status codes from `res.status(N)`.
- **Auth:** Same auth libraries as App Router, plus look for middleware in `_middleware.ts` files, `getServerSideProps` patterns, or `getSession(req)` calls.

### 2c. Express.js

**Where to look:** This is more complex because Express routes can be defined anywhere. Use this search strategy in order:

1. Read the main entry point (check `package.json` `"main"` field, or look for `index.js`, `index.ts`, `app.js`, `app.ts`, `server.js`, `server.ts`, `src/index.ts`, `src/app.ts`, `src/server.ts`).
2. From the entry point, trace `require()` / `import` statements for route files. Look for patterns like `app.use('/api/users', usersRouter)` to understand route prefixes.
3. Scan all `.js` and `.ts` files in `routes/`, `src/routes/`, `api/`, `src/api/`, `controllers/`, `src/controllers/` directories.
4. As a fallback, grep across all `.js`/`.ts` files for `app.get(`, `app.post(`, `router.get(`, `router.post(`, etc.

**How to extract HTTP methods and paths:** Look for these patterns:
```
app.get('/path', handler)
app.post('/path', handler)
app.put('/path', handler)
app.patch('/path', handler)
app.delete('/path', handler)
router.get('/path', handler)
router.post('/path', handler)
// etc.
```
The method name after the dot IS the HTTP method. The first string argument IS the path. Combine with the prefix from `app.use()` mounting to get the full path.

**Dynamic segments** use `:param` syntax: `/users/:id/posts/:postId`.

**How to extract request details:**
- **Query parameters:** Look for `req.query.paramName` or destructuring from `req.query`.
- **Path parameters:** Look for `req.params.paramName` or destructuring from `req.params`. Also infer from `:param` segments in the route path.
- **Request body:** Look for `req.body` access. Check for body-parsing middleware (`express.json()`, `bodyParser.json()`). Trace fields read from `req.body`.
- **Response shape:** Look for `res.json({...})`, `res.status(N).json({...})`, `res.send(...)`. Record object shapes and status codes.
- **Auth:** Look for middleware functions in the route chain: `app.get('/path', authMiddleware, handler)`. Check for `passport`, `jsonwebtoken`/`jwt`, `express-jwt`, `req.user`, `req.isAuthenticated()`, header reads for `Authorization`.
- **Validation:** Look for `express-validator`, `celebrate`/`joi`, `zod` middleware.

### 2d. FastAPI (Python)

**Where to look:** Scan all `.py` files in the project. Focus on:
1. `main.py`, `app.py`, `src/main.py`, `src/app.py` -- the main application file.
2. Files in `routers/`, `routes/`, `api/`, `endpoints/`, `src/routers/`, `src/api/`, `app/routers/`, `app/api/` directories.
3. Trace `app.include_router(...)` calls to find router modules and their prefixes.

**How to extract HTTP methods and paths:** Look for decorator patterns:
```python
@app.get("/path")
@app.post("/path")
@app.put("/path")
@app.patch("/path")
@app.delete("/path")
@router.get("/path")
@router.post("/path")
# etc.
```
The decorator name after the dot IS the HTTP method. The string argument IS the path. Combine with the prefix from `include_router(router, prefix="/api")`.

**Dynamic segments** use `{param}` syntax: `/users/{user_id}/posts/{post_id}`.

**How to extract request details:**
- **Path parameters:** Function arguments that match `{param}` names in the path, with type annotations: `def get_user(user_id: int)`.
- **Query parameters:** Function arguments NOT in the path and not annotated as Body/Header/Cookie. Or explicitly annotated with `Query()`: `def list_users(skip: int = Query(0), limit: int = Query(10))`.
- **Request body:** Arguments annotated with Pydantic model types: `def create_user(user: UserCreate)`. Or explicitly annotated with `Body()`.
- **Response shape:** Check for `response_model` in the decorator: `@app.get("/users", response_model=List[User])`. Also check return type annotations and the actual return statements.
- **Status codes:** Check for `status_code` in the decorator: `@app.post("/users", status_code=201)`. Also look for `HTTPException(status_code=404, ...)` raises.
- **Auth:** Look for `Depends()` with auth functions: `current_user: User = Depends(get_current_user)`. Check for OAuth2 schemes, API key headers, or security utilities from `fastapi.security`.

**How to extract data models:** Read all Pydantic model classes (classes inheriting from `BaseModel`). Record:
- Class name
- All fields with their types, default values, and `Field()` descriptions
- Relationships between models (e.g., `UserCreate` vs `UserResponse` vs `User`)

---

## Step 3: Find Data Models and Validation Schemas

After discovering routes, locate the data models that define request/response shapes. Search based on what the project uses.

### TypeScript interfaces and types

Search for `interface` and `type` declarations in:
- Files imported by route handlers
- `types/`, `src/types/`, `interfaces/`, `src/interfaces/`, `models/`, `src/models/` directories
- Co-located type files near the route handlers (e.g., `types.ts` in the same folder)

Record field names, types, and whether fields are optional (`?:`).

### Zod schemas

Look for `z.object({...})` definitions. These are common in Next.js projects. Extract:
- Field names and Zod types (map to plain language: `z.string()` --> `string`, `z.number().int()` --> `integer`, etc.)
- Validation constraints: `.min()`, `.max()`, `.email()`, `.url()`, `.optional()`, `.nullable()`
- Default values: `.default(value)`

### Prisma schemas

If `prisma/schema.prisma` exists, read it. Extract model definitions -- these represent the database shape and often closely match API response shapes. Record field names, types, relations, and attributes like `@id`, `@unique`, `@default`.

### Drizzle schemas

Look for `pgTable()`, `mysqlTable()`, `sqliteTable()` calls in `schema.ts`, `db/schema.ts`, `src/db/schema.ts`, or `drizzle/` directories.

### Mongoose schemas

Look for `new Schema({...})` or `mongoose.model()` calls. Extract field definitions.

### Pydantic models (FastAPI)

Already covered in Step 2d. Ensure all referenced models are fully documented including nested models.

### Yup schemas

Look for `yup.object().shape({...})` definitions. Extract field names, types, and validations.

---

## Step 4: Generate llms.txt

Compose a concise endpoint index. Use this exact structure:

```
# {Project Name} API

> {One-line description of what this API does.}

## Endpoints

- GET /api/resource - Brief purpose description
- POST /api/resource - Brief purpose description
- GET /api/resource/{id} - Brief purpose description
- PUT /api/resource/{id} - Brief purpose description
- DELETE /api/resource/{id} - Brief purpose description

## Authentication

{One-line summary of auth method, or "No authentication required." if none detected.}

## Full Documentation

See [llms-full.txt](/llms-full.txt) for complete endpoint details, request/response schemas, and examples.
```

Rules for llms.txt:
- Keep it under 50 lines when possible. It is a quick-reference index, not full documentation.
- One line per endpoint: `METHOD /path - purpose`.
- Group endpoints logically by resource if there are many.
- Use the actual dynamic segment syntax from the framework (`[id]` for Next.js, `:id` for Express, `{id}` for FastAPI).
- Include the auth summary only if authentication was detected.

---

## Step 5: Generate llms-full.txt

Compose comprehensive documentation. Use this exact structure:

```
# {Project Name} API -- Full Documentation

> {2-3 sentence description of the API, its purpose, and primary use cases.}

## Base URL

{Base URL if known, or note that it depends on deployment. For local dev, use http://localhost:{port}.}

## Authentication

{Detailed auth description. Include:
- Auth type (Bearer token, API key, session cookie, OAuth2, etc.)
- Where to include credentials (Authorization header, query param, cookie)
- How to obtain credentials (if discoverable from the code)
- Which endpoints require auth and which are public
If no auth detected, state "This API does not require authentication."}

## Data Models

### {ModelName}

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique identifier |
| name | string | Yes | Display name |
| email | string | Yes | Email address |
| createdAt | string (ISO 8601) | Yes | Creation timestamp |
| updatedAt | string (ISO 8601) | Yes | Last update timestamp |

{Repeat for each model. Include all fields with their actual types, required/optional status, and descriptions inferred from field names, validation rules, or comments in the code.}

## Endpoints

### {METHOD} {/path}

{One paragraph description of what this endpoint does.}

**Parameters**

| Name | In | Type | Required | Description |
|------|------|------|----------|-------------|
| id | path | string | Yes | Resource identifier |
| page | query | integer | No | Page number (default: 1) |
| limit | query | integer | No | Items per page (default: 20) |

{Omit the Parameters section entirely if the endpoint takes no parameters.}

**Request Body**

```json
{
  "name": "Example Name",
  "email": "user@example.com"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Display name |
| email | string | Yes | Email address |

{Omit the Request Body section entirely if the endpoint takes no body (GET, DELETE usually).}

**Response**

`200 OK`

```json
{
  "id": "abc123",
  "name": "Example Name",
  "email": "user@example.com",
  "createdAt": "2025-01-15T10:30:00Z"
}
```

{For list endpoints, show the array or paginated wrapper structure.}

**Error Responses**

| Status | Description |
|--------|-------------|
| 400 | Invalid request body / validation error |
| 401 | Missing or invalid authentication |
| 404 | Resource not found |
| 500 | Internal server error |

{Only list error codes that are actually used in the route handler code. Do not guess.}

---

{Repeat the endpoint block for every discovered route.}

## Examples

### Create a resource

```bash
curl -X POST http://localhost:3000/api/resource \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Example",
    "email": "user@example.com"
  }'
```

### List resources

```bash
curl http://localhost:3000/api/resource?page=1&limit=10
```

### Get a single resource

```bash
curl http://localhost:3000/api/resource/abc123
```

{Include a curl example for every endpoint. For Python consumers, also include a requests/httpx example if the project is FastAPI:}

```python
import httpx

response = httpx.get("http://localhost:8000/api/resource")
data = response.json()
```

{Use realistic but clearly fake example data. Use the actual field names from the models.}
```

Rules for llms-full.txt:
- Document EVERY discovered endpoint with no exceptions.
- Use realistic example data that matches the field types (strings for strings, numbers for numbers, ISO dates for timestamps, UUIDs if the code uses them).
- Parameter tables must include every path param, query param, and header that the code reads.
- Request body tables must include every field with its type and whether it is required.
- Only list error status codes that actually appear in the handler code. Do not invent error codes.
- Keep descriptions factual -- describe what the code does, do not speculate about intent.
- If a field's purpose is unclear from the code, use the field name as the description.

---

## Step 6: Quality Checklist

Before finalizing, verify all of the following. Fix any issues found.

- [ ] **Every discovered route is documented.** Cross-reference the route list from Step 2 against the endpoints in llms-full.txt. There must be a 1:1 match.
- [ ] **All path parameters are listed.** Every dynamic segment in every URL has a corresponding row in the Parameters table.
- [ ] **All query parameters are listed.** Every `searchParams.get()`, `req.query.x`, or `Query()` access has a corresponding row.
- [ ] **Request body fields match the code.** Every field destructured from the request body or defined in the validation schema appears in the Request Body table.
- [ ] **Response shapes match the code.** The example JSON in each Response section reflects what the handler actually returns (field names, nesting, array wrapping).
- [ ] **Status codes are accurate.** Every status code listed in Error Responses actually appears in the handler. No invented codes.
- [ ] **Examples are syntactically valid.** Every curl command and code snippet can run without syntax errors (proper quoting, correct flags, valid JSON).
- [ ] **Auth is documented if present.** If any route checks auth, the Authentication section describes the mechanism and the per-endpoint auth requirements are noted.
- [ ] **Dynamic segment syntax is consistent.** Use the framework's native syntax throughout (not a mix of `[id]`, `:id`, and `{id}`).
- [ ] **llms.txt and llms-full.txt are consistent.** Every endpoint in llms.txt also appears in llms-full.txt and vice versa. Descriptions do not contradict each other.

---

## Step 7: Serve the Documentation

Based on the detected framework, tell the user where to put the files and offer to create serving routes.

### Next.js App Router

Create two route handlers that serve the docs as plain text:

**`app/llms.txt/route.ts`** (or `src/app/llms.txt/route.ts` if the project uses `src/`):
```typescript
export async function GET() {
  const content = `{paste llms.txt content here}`;
  return new Response(content, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
```

**`app/llms-full.txt/route.ts`** (or `src/app/llms-full.txt/route.ts`):
```typescript
export async function GET() {
  const content = `{paste llms-full.txt content here}`;
  return new Response(content, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
```

Alternatively, place static `llms.txt` and `llms-full.txt` files in the `public/` directory. This is simpler but means the docs are not auto-updated. Recommend the `public/` approach for simplicity unless the user wants dynamic generation.

### Next.js Pages Router

Create two API routes:

**`pages/api/llms.txt.ts`** (or `src/pages/api/llms.txt.ts`):
```typescript
import type { NextApiRequest, NextApiResponse } from "next";

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  res.setHeader("Content-Type", "text/plain; charset=utf-8");
  res.send(`{paste llms.txt content here}`);
}
```

**`pages/api/llms-full.txt.ts`** (same pattern).

Or use the `public/` directory as described above.

### Express.js

Add two routes to the Express app (in the main app file or a dedicated docs router):

```typescript
app.get("/llms.txt", (req, res) => {
  res.type("text/plain").send(`{paste llms.txt content here}`);
});

app.get("/llms-full.txt", (req, res) => {
  res.type("text/plain").send(`{paste llms-full.txt content here}`);
});
```

Alternatively, place static files in the Express static directory (usually `public/`) if `express.static()` middleware is configured.

### FastAPI

Add two endpoints to the FastAPI app:

```python
from fastapi.responses import PlainTextResponse

@app.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt():
    return """{paste llms.txt content here}"""

@app.get("/llms-full.txt", response_class=PlainTextResponse)
async def llms_full_txt():
    return """{paste llms-full.txt content here}"""
```

---

## Notes for the Agent

- **Be thorough in discovery.** Read every route file completely. Do not skim or assume. If a file is long, read it in sections.
- **Trace imports.** Route handlers often import types, validators, and utilities from other files. Follow those imports to get complete schemas.
- **Handle monorepos.** If the project root contains multiple packages (e.g., `packages/api/`), ask the user which package to document or look for the one containing API routes.
- **Handle multiple routers.** Some projects split routes across many files. Make sure you find them all by tracing `app.use()` (Express), `include_router()` (FastAPI), or scanning the filesystem (Next.js).
- **Respect existing docs.** If `llms.txt` or `llms-full.txt` already exist, read them first and offer to update rather than overwrite.
- **Dynamic segments normalization.** Always use the framework-native syntax in the final output. When mentioning a path generically (not in framework-specific context), prefer `{id}` as it is the most widely understood.
- **Port detection.** Check `package.json` scripts, `.env` files, and code for port configuration to use in example URLs. Default to `3000` for Node.js and `8000` for FastAPI if not found.
- **Large APIs.** If there are more than 20 endpoints, organize them by resource/tag in both llms.txt and llms-full.txt using subheadings.
