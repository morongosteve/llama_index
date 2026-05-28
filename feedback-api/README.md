# Feedback API

A Next.js REST API for collecting, retrieving, filtering, and summarising user feedback. Backed by a JSON file.

## Getting Started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to see the app.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/feedback | List all feedback (supports filtering) |
| POST | /api/feedback | Create new feedback |
| GET | /api/feedback/:id | Get single item |
| PUT | /api/feedback/:id | Update item |
| DELETE | /api/feedback/:id | Delete item |
| GET | /api/feedback/summary | Aggregate stats |
| GET | /api/health | Health check |
| GET | /llms.txt | Agent-friendly docs (concise) |
| GET | /llms-full.txt | Agent-friendly docs (full) |

## Deploy

Deploy anywhere that runs Node.js — for example, a HuggingFace Space with Docker, Railway, Fly.io, or any VPS with `npm run build && npm start`.
