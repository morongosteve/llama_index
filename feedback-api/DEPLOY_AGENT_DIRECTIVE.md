# Agent Directive: Deploy Feedback API to Hugging Face Spaces

## Identity

You are an autonomous deployment agent. You have full control over the local machine (desktop) and terminal. Execute every step without asking for confirmation. If a step fails, diagnose, fix, and retry up to 3 times before reporting.

## Context

There is a fully built Next.js Feedback API project that needs to be deployed to Hugging Face Spaces using Docker. The project is located in the `feedback-api/` directory (either at `/home/user/feedback-api` or wherever you find it on this machine). The user has a Pro Hugging Face account.

## Credentials

- **HF Token**: Set via environment variable `HF_TOKEN` before running. Get yours at https://huggingface.co/settings/tokens
- **HF Username**: Determine by running `hf whoami` after login. Use whatever username is returned.

## Step-by-Step Execution

### Phase 1: Environment Setup

1. Install or update the Hugging Face CLI:
   ```
   pip install --upgrade huggingface_hub
   ```
2. Login with the token:
   ```
   hf auth login --token $HF_TOKEN --add-to-git-credential
   ```
3. Verify login:
   ```
   hf whoami
   ```
   Store the returned username — you will need it for every subsequent step.

4. Ensure `git`, `node` (v20+), and `npm` are installed. If not, install them.

### Phase 2: Locate and Validate the Project

1. Find the `feedback-api` directory. Check these locations in order:
   - `./feedback-api/`
   - `~/feedback-api/`
   - `~/llama_index/feedback-api/`
   - Search: `find ~ -maxdepth 3 -name "feedback-api" -type d 2>/dev/null`

2. `cd` into the project directory.

3. Verify these files exist (abort if any are missing):
   - `Dockerfile`
   - `README.md` (must contain `sdk: docker` in YAML frontmatter)
   - `data/feedback.json`
   - `src/app/api/feedback/route.ts`
   - `src/app/llms.txt/route.ts`
   - `src/app/llms-full.txt/route.ts`
   - `src/lib/db.ts`
   - `next.config.ts` (must contain `output: "standalone"`)
   - `package.json`
   - `.dockerignore`

4. Run `npm install` if `node_modules/` doesn't exist.

5. Run `npm run build` to verify the project compiles. If it fails, read the error, fix it, and retry.

### Phase 3: Create Hugging Face Space

1. Create the Space:
   ```
   hf repo create feedback-api --type space --space-sdk docker
   ```
   If it already exists, that's fine — continue.

2. Verify it was created:
   ```
   hf repo ls --type space | grep feedback-api
   ```

### Phase 4: Prepare Git and Push

1. If the directory is NOT already a git repo, initialize one:
   ```
   git init
   ```

2. Make sure `README.md` has the correct HF Spaces frontmatter at the very top of the file:
   ```yaml
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
   ```
   If the frontmatter is missing or wrong, fix it.

3. Make sure `.gitignore` excludes:
   - `node_modules/`
   - `.next/`
   
   But does NOT exclude `src/` (some repos have a root .gitignore that blocks `src/` — if so, add `!feedback-api/src/` or use `git add -f`).

4. Stage all files:
   ```
   git add -A
   git add -f src/  # Force if gitignore blocks it
   ```

5. Commit:
   ```
   git commit -m "Deploy Feedback API to HF Spaces"
   ```
   If nothing to commit (already committed), continue.

6. Add the HF remote (replace USERNAME with the actual username from Phase 1):
   ```
   git remote add hf https://huggingface.co/spaces/USERNAME/feedback-api
   ```
   If remote already exists, update it:
   ```
   git remote set-url hf https://huggingface.co/spaces/USERNAME/feedback-api
   ```

7. Push:
   ```
   git push hf HEAD:main --force
   ```
   This force-push is intentional — we want the Space to match exactly what we have locally.

### Phase 5: Verify Deployment

1. Wait 2 minutes for HF to build the Docker image.

2. Check the Space status:
   ```
   hf repo info spaces/USERNAME/feedback-api
   ```

3. Test the live endpoints (replace USERNAME):
   ```
   curl https://USERNAME-feedback-api.hf.space/api/feedback
   curl https://USERNAME-feedback-api.hf.space/api/feedback/summary
   curl https://USERNAME-feedback-api.hf.space/llms.txt
   curl https://USERNAME-feedback-api.hf.space/llms-full.txt
   ```

4. If any endpoint returns an error or the Space is still building, wait another 2 minutes and retry. The Docker build can take up to 5 minutes on first deploy.

5. Test a write operation:
   ```
   curl -X POST https://USERNAME-feedback-api.hf.space/api/feedback \
     -H "Content-Type: application/json" \
     -d '{"text":"Deployed via HF Spaces","rating":5,"category":"deployment","author":"agent@deploy","tags":["hf","live"]}'
   ```

### Phase 6: Report

When done, output a summary in this exact format:

```
DEPLOYMENT COMPLETE
---
Space URL: https://huggingface.co/spaces/USERNAME/feedback-api
Live API:  https://USERNAME-feedback-api.hf.space
Endpoints verified:
  - GET  /api/feedback        ✓/✗
  - POST /api/feedback        ✓/✗
  - GET  /api/feedback/{id}   ✓/✗
  - GET  /api/feedback/summary ✓/✗
  - GET  /llms.txt            ✓/✗
  - GET  /llms-full.txt       ✓/✗
```

## Error Recovery

- **"repo already exists"**: Continue — this is fine.
- **"remote already exists"**: Use `git remote set-url` instead of `git remote add`.
- **Build fails on HF**: Check logs at `https://huggingface.co/spaces/USERNAME/feedback-api/logs`, diagnose the Docker build error, fix locally, commit, and push again.
- **Port mismatch**: Ensure the Dockerfile uses `ENV PORT=7860` and `EXPOSE 7860`. HF Spaces requires port 7860.
- **Authentication failures**: Re-run `hf auth login --token $HF_TOKEN`.
- **Network timeouts on push**: Retry up to 3 times with 10-second waits between attempts.

## Security Note

After successful deployment, remind the user to rotate the HF token at https://huggingface.co/settings/tokens since it was shared in a chat session.
