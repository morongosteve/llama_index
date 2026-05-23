---
title: Feedback API
emoji: 📋
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: true
license: mit
---

# Feedback API

A REST API for collecting, querying, and summarizing user feedback. Built with Next.js, backed by a JSON file store.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/feedback` | List feedback with filtering, sorting, pagination |
| POST | `/api/feedback` | Create a new feedback entry |
| GET | `/api/feedback/{id}` | Get a single entry |
| PATCH | `/api/feedback/{id}` | Partial update |
| DELETE | `/api/feedback/{id}` | Remove an entry |
| GET | `/api/feedback/summary` | Aggregate statistics |

## Agent-Friendly Docs

- [`/llms.txt`](./llms.txt) — Concise endpoint index
- [`/llms-full.txt`](./llms-full.txt) — Full API reference for LLMs

## Query Parameters (GET /api/feedback)

`category`, `rating`, `minRating`, `maxRating`, `tag`, `author`, `sort` (newest/oldest/rating-asc/rating-desc), `limit`, `offset`

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
