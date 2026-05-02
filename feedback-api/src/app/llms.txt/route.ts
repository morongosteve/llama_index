import { NextResponse } from "next/server";

const LLMS_TXT = `# Feedback API

> A REST API for collecting, querying, and summarizing user feedback. Backed by a JSON data store.

## Endpoints

- [List feedback](/api/feedback): GET — returns all feedback with optional filters
- [Create feedback](/api/feedback): POST — create a new feedback entry
- [Get feedback by ID](/api/feedback/{id}): GET — retrieve a single entry
- [Update feedback](/api/feedback/{id}): PATCH — partial update of an entry
- [Delete feedback](/api/feedback/{id}): DELETE — remove an entry
- [Summary](/api/feedback/summary): GET — aggregate stats across all feedback

## Docs

- [Full API documentation for LLMs](/llms-full.txt)
`;

export async function GET() {
  return new NextResponse(LLMS_TXT, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
