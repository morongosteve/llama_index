# Gemma 4 Mobile Chat Frontend

A single-file, zero-build chat UI for your Gemma 4 Railway backend. Works great
saved to your phone's home screen as a PWA-style web app.

- Streaming responses (SSE via `/stream`, falls back to `/chat`)
- Dark, mobile-first, safe-area aware (notch/home-bar friendly)
- Backend URL stored in `localStorage` — set it once in ⚙ settings
- No framework, no build step — just `index.html`

## Deploy

### Cloudflare Pages
1. [dash.cloudflare.com](https://dash.cloudflare.com) → Workers & Pages → Create → Pages
2. Connect to Git → select `morongosteve/llama_index`
3. Build settings:
   - Framework preset: **None**
   - Build command: *(leave empty)*
   - Build output directory: `gemma4-frontend`
4. Deploy → you get a `https://<project>.pages.dev` URL

### Netlify
1. [app.netlify.com](https://app.netlify.com) → Add new site → Import from Git
2. Select the repo
3. Build settings:
   - Build command: *(leave empty)*
   - Publish directory: `gemma4-frontend`
4. Deploy

### Or just open it locally
Open `index.html` in any browser — it's fully self-contained.

## Connect to your backend
1. Open the deployed page (or the file) on your phone
2. Tap ⚙ → paste your Railway URL (e.g. `https://your-app.railway.app`)
3. Tap **Save & connect** — the status dot turns green and shows the model
4. Chat

## Backend CORS
The Railway server (`gemma4-railway/server.py`) defaults `ALLOWED_ORIGINS` to `*`,
so any frontend origin works out of the box. To lock it down, set the
`ALLOWED_ORIGINS` env var on Railway to your Pages/Netlify URL.
