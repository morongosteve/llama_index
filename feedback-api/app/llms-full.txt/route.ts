import { NextResponse } from "next/server";

const BASE = process.env.NEXT_PUBLIC_BASE_URL ?? "https://feedback-api.vercel.app";

const DOCS = `# Feedback API — Full Reference

> Complete machine-readable documentation for the Feedback API.
> Generated dynamically at ${BASE}/llms-full.txt

---

## Overview

The Feedback API is a JSON REST API for storing and querying user feedback.
No authentication is required. Every request and response body uses Content-Type: application/json.

Base URL: ${BASE}

---

## Data Model

A Feedback item has these fields:

| Field      | Type   | Description                                    |
|------------|--------|------------------------------------------------|
| id         | string | UUID, assigned by the server on creation       |
| author     | string | Handle or name of the person who left feedback |
| rating     | number | Integer 1 (worst) – 5 (best)                   |
| category   | string | One of: "bug", "feature", "general"            |
| message    | string | Free-text feedback content                     |
| createdAt  | string | ISO 8601 timestamp                             |
| updatedAt  | string | ISO 8601 timestamp (changes on PUT)            |

---

## Endpoints

### GET /api/feedback

List all feedback items. Supports optional query-param filters.

Query parameters:
- author     (string)  — exact match on author
- category   (string)  — one of: bug, feature, general
- rating     (number)  — exact match on rating (1–5)
- minRating  (number)  — inclusive lower bound on rating
- maxRating  (number)  — inclusive upper bound on rating
- limit      (number)  — max items to return (default: all)
- offset     (number)  — items to skip for pagination (default: 0)

Response 200:
{
  "data": [ <Feedback>, ... ],
  "count": <number>
}

Example:
  GET ${BASE}/api/feedback?category=bug&minRating=1&maxRating=3&limit=10

---

### POST /api/feedback

Create a new feedback item. All four body fields are required.

Request body:
{
  "author":   "<string>",
  "rating":   <integer 1–5>,
  "category": "<bug|feature|general>",
  "message":  "<string>"
}

Response 201:
{
  "data": <Feedback>
}

Response 400 (validation failure):
{
  "error": "<reason>"
}

Example:
  POST ${BASE}/api/feedback
  { "author": "alice", "rating": 5, "category": "feature", "message": "Excellent UX." }

---

### GET /api/feedback/:id

Retrieve a single feedback item by its UUID.

Path parameter:
- id (string) — UUID of the feedback item

Response 200:
{
  "data": <Feedback>
}

Response 404:
{
  "error": "Not found"
}

Example:
  GET ${BASE}/api/feedback/a1b2c3d4-0001

---

### PUT /api/feedback/:id

Partially update a feedback item. Send only the fields you want to change.

Path parameter:
- id (string) — UUID of the feedback item

Request body (all fields optional):
{
  "author":   "<string>",
  "rating":   <integer 1–5>,
  "category": "<bug|feature|general>",
  "message":  "<string>"
}

Response 200:
{
  "data": <updated Feedback>
}

Response 400 (validation failure):
{
  "error": "<reason>"
}

Response 404:
{
  "error": "Not found"
}

Example:
  PUT ${BASE}/api/feedback/a1b2c3d4-0001
  { "rating": 4, "message": "Updated after the fix shipped." }

---

### DELETE /api/feedback/:id

Delete a feedback item permanently.

Path parameter:
- id (string) — UUID of the feedback item

Response 200:
{
  "data": { "deleted": true, "id": "<id>" }
}

Response 404:
{
  "error": "Not found"
}

Example:
  DELETE ${BASE}/api/feedback/a1b2c3d4-0001

---

### GET /api/feedback/summary

Return aggregate statistics across all feedback items.

Response 200:
{
  "data": {
    "total":         <number>,
    "averageRating": <number, 2 decimal places>,
    "byCategory": {
      "bug":     <number>,
      "feature": <number>,
      "general": <number>
    },
    "byRating": {
      "1": <number>,
      "2": <number>,
      "3": <number>,
      "4": <number>,
      "5": <number>
    }
  }
}

Example:
  GET ${BASE}/api/feedback/summary

---

### GET /api/health

Liveness check. Always returns 200.

Response 200:
{
  "status": "ok",
  "timestamp": "<ISO 8601>"
}

---

## Error Format

All error responses share a consistent shape:
{
  "error": "<human-readable message>"
}

HTTP status codes used:
- 200 — success
- 201 — resource created
- 400 — validation error (bad input)
- 404 — resource not found
- 500 — internal server error

---

## Pagination Pattern

Use limit + offset for pagination:
  GET /api/feedback?limit=10&offset=0   # page 1
  GET /api/feedback?limit=10&offset=10  # page 2
  GET /api/feedback?limit=10&offset=20  # page 3

---

## Usage Notes for Agents

1. Always check the "count" field in list responses to know if you received all items.
2. Use /api/feedback/summary first for an overview before listing all items.
3. The :id parameter is a UUID string — preserve it exactly as returned by GET/POST.
4. Writes (POST, PUT, DELETE) are not atomic; avoid concurrent mutations to the same id.
5. The category enum is case-sensitive: use lowercase "bug", "feature", or "general".
`;

export async function GET() {
  return new NextResponse(DOCS, {
    status: 200,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
