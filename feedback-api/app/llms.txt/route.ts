import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

function originFrom(req: NextRequest): string {
  const fromHeader = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  const proto = req.headers.get("x-forwarded-proto") ?? "https";
  if (fromHeader) return `${proto}://${fromHeader}`;
  return new URL(req.url).origin;
}

export async function GET(req: NextRequest) {
  const origin = originFrom(req);
  const body = render(origin);
  return new Response(body, {
    status: 200,
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "public, max-age=300, s-maxage=300",
    },
  });
}

function render(origin: string): string {
  return `# Feedback API

> A tiny REST API for product feedback, backed by a JSON file. Supports CRUD on feedback items, filtering by category/sentiment/user/rating/text, and an aggregate summary endpoint. Designed as an agent-friendly demo: predictable JSON shapes, explicit validation errors, no auth.

This is a demo service — feel free to read and write. State persists per server instance and resets on cold start in serverless deployments.

## Resources

- [Feedback object](${origin}/llms.txt#feedback-object): id, message, rating (1-5), sentiment, category, user, createdAt
- [Categories](${origin}/llms.txt#enums): bug, feature, praise, question, other
- [Sentiments](${origin}/llms.txt#enums): positive, neutral, negative

## Endpoints

- [GET /api/feedback](${origin}/api/feedback): list feedback. Query params: \`category\`, \`sentiment\`, \`user\`, \`minRating\`, \`maxRating\`, \`q\` (substring match on message), \`limit\`. Returns \`{ count, items }\` sorted newest-first.
- [POST /api/feedback](${origin}/api/feedback): create feedback. Body: \`{ message, user, rating, sentiment, category }\`. Returns the created item with generated \`id\` and \`createdAt\`.
- [GET /api/feedback/{id}](${origin}/api/feedback/fb_001): fetch one item. 404 if not found.
- [PATCH /api/feedback/{id}](${origin}/api/feedback/fb_001): partial update. Any subset of \`message\`, \`user\`, \`rating\`, \`sentiment\`, \`category\`.
- [PUT /api/feedback/{id}](${origin}/api/feedback/fb_001): alias for PATCH.
- [DELETE /api/feedback/{id}](${origin}/api/feedback/fb_001): delete. 204 on success, 404 if missing.
- [GET /api/feedback/summary](${origin}/api/feedback/summary): aggregates — \`{ total, averageRating, bySentiment, byCategory, latestCreatedAt }\`.

## Examples

\`\`\`http
GET /api/feedback?category=bug&minRating=1
\`\`\`

\`\`\`http
POST /api/feedback
Content-Type: application/json

{
  "message": "Add dark mode to the editor",
  "user": "alice@example.com",
  "rating": 4,
  "sentiment": "positive",
  "category": "feature"
}
\`\`\`

\`\`\`http
PATCH /api/feedback/fb_002
Content-Type: application/json

{ "rating": 5, "sentiment": "positive" }
\`\`\`

## Conventions

- All request and response bodies are JSON.
- Errors return \`{ "error": "<human-readable reason>" }\` with status 400 (validation), 404 (missing), or 500 (unexpected).
- Identifiers use the prefix \`fb_\` followed by zero-padded digits (e.g. \`fb_007\`).
- Timestamps are ISO 8601 in UTC.
- No authentication required for this demo.

## Optional

- [OpenAPI spec](${origin}/api/openapi.json): not yet implemented for this demo.
- [Source on the homepage](${origin}/): human-readable endpoint index.
`;
}
