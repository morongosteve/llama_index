import { NextResponse } from "next/server";

const LLMS_FULL_TXT = `# Feedback API — Full Documentation

> A REST API for collecting, querying, and summarizing user feedback.
> Base URL: /api/feedback

---

## Data Model

Each feedback entry has the following shape:

\`\`\`json
{
  "id": "fb_001",
  "text": "The onboarding flow was seamless.",
  "rating": 5,
  "category": "ux",
  "author": "alice@example.com",
  "createdAt": "2026-04-01T10:00:00Z",
  "tags": ["onboarding", "positive"]
}
\`\`\`

### Fields

| Field     | Type     | Description                              |
|-----------|----------|------------------------------------------|
| id        | string   | Unique ID, auto-generated (fb_ prefix)   |
| text      | string   | The feedback content (required)          |
| rating    | integer  | 1-5 star rating (required)               |
| category  | string   | Category slug (required)                 |
| author    | string   | Author email or identifier (required)    |
| createdAt | string   | ISO 8601 timestamp (auto-generated)      |
| tags      | string[] | Array of tag strings (required)          |

Common categories: ux, bug, performance, feature-request

---

## Endpoints

### GET /api/feedback

List all feedback entries with optional filtering, sorting, and pagination.

**Query Parameters:**

| Param     | Type    | Description                                          |
|-----------|---------|------------------------------------------------------|
| category  | string  | Filter by exact category match                       |
| rating    | integer | Filter by exact rating (1-5)                         |
| minRating | integer | Filter entries with rating >= this value             |
| maxRating | integer | Filter entries with rating <= this value             |
| tag       | string  | Filter entries that include this tag                 |
| author    | string  | Filter by exact author match                         |
| sort      | string  | One of: newest, oldest, rating-asc, rating-desc      |
| limit     | integer | Max entries to return (for pagination)               |
| offset    | integer | Number of entries to skip (for pagination)           |

**Response:**

\`\`\`json
{
  "items": [ ...feedback entries... ],
  "total": 10
}
\`\`\`

**Examples:**

\`\`\`
GET /api/feedback?category=bug&sort=newest
GET /api/feedback?minRating=4&limit=5
GET /api/feedback?tag=mobile&sort=rating-desc
\`\`\`

---

### POST /api/feedback

Create a new feedback entry.

**Request Body (JSON):**

\`\`\`json
{
  "text": "Great improvement to the search feature!",
  "rating": 5,
  "category": "ux",
  "author": "user@example.com",
  "tags": ["search", "positive"]
}
\`\`\`

All fields are required. Rating must be an integer 1-5. Tags must be an array of strings.

**Response:** 201 Created with the new entry (includes generated id and createdAt).

**Error Response:** 400 with \`{ "error": "description" }\` if validation fails.

---

### GET /api/feedback/{id}

Retrieve a single feedback entry by ID.

**Response:** The feedback object, or 404 \`{ "error": "Not found" }\`.

---

### PATCH /api/feedback/{id}

Partially update a feedback entry. Only include the fields you want to change.

**Request Body (JSON):**

\`\`\`json
{
  "rating": 4,
  "tags": ["updated-tag"]
}
\`\`\`

Allowed fields: text, rating, category, author, tags. ID and createdAt cannot be changed.

**Response:** The updated entry, or 404 if not found.

---

### DELETE /api/feedback/{id}

Delete a feedback entry.

**Response:** \`{ "deleted": true }\` on success, or 404 if not found.

---

### GET /api/feedback/summary

Returns aggregate statistics across all feedback.

**Response:**

\`\`\`json
{
  "totalCount": 10,
  "averageRating": 3.3,
  "ratingDistribution": { "1": 1, "2": 3, "3": 1, "4": 2, "5": 3 },
  "categoryCounts": { "ux": 3, "bug": 3, "performance": 2, "feature-request": 2 },
  "topTags": [
    { "tag": "positive", "count": 3 },
    { "tag": "mobile", "count": 1 }
  ],
  "recentCount7d": 2
}
\`\`\`

---

## Error Handling

All error responses use this format:

\`\`\`json
{
  "error": "Human-readable error message"
}
\`\`\`

| Status | Meaning                                |
|--------|----------------------------------------|
| 400    | Invalid request body or parameters     |
| 404    | Feedback entry not found               |
| 201    | Successfully created                   |
| 200    | Success                                |

---

## Notes

- No authentication required (public API)
- Data is stored in a JSON file on disk (not suitable for concurrent writes at scale)
- IDs are auto-generated with crypto random hex (fb_ prefix)
- Timestamps are ISO 8601 UTC
- The summary endpoint recomputes stats on every request (no caching)
`;

export async function GET() {
  return new NextResponse(LLMS_FULL_TXT, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
