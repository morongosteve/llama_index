---
title: Feedback API
emoji: 📝
colorFrom: green
colorTo: blue
sdk: docker
pinned: false
license: mit
app_port: 7860
---

# Feedback API

A REST API for collecting, retrieving, filtering, and summarising user feedback. Each feedback item carries a 1-5 star rating, a category (bug / feature / general), a freetext message, and an author handle. All data is persisted in a JSON file.

## Endpoints

- `GET /api/feedback` - List all feedback (supports filtering)
- `POST /api/feedback` - Create new feedback
- `GET /api/feedback/:id` - Get a single item
- `PUT /api/feedback/:id` - Update an item
- `DELETE /api/feedback/:id` - Delete an item
- `GET /api/feedback/summary` - Aggregate stats
- `GET /api/health` - Health check
- `GET /llms.txt` - Agent-friendly docs (index)
- `GET /llms-full.txt` - Agent-friendly docs (full reference)

## Local Development

```bash
npm install
npm run dev
```

## Docker

```bash
docker build -t feedback-api .
docker run -p 7860:7860 feedback-api
```
