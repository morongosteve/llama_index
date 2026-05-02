import { promises as fs } from "fs";
import path from "path";
import { Feedback, NewFeedback, FeedbackPatch } from "./types";

// Seed is a committed, immutable starting point; runtime mutations go
// elsewhere so the repo seed stays clean. On Vercel only /tmp is writable
// (and ephemeral per-instance); locally we use a sibling runtime file.
const SEED_PATH = path.join(process.cwd(), "data", "feedback.json");
const RUNTIME_PATH = process.env.VERCEL
  ? path.join("/tmp", "feedback.json")
  : path.join(process.cwd(), "data", "feedback.runtime.json");

let memoryCache: Feedback[] | null = null;

async function readSeed(): Promise<Feedback[]> {
  const raw = await fs.readFile(SEED_PATH, "utf8");
  return JSON.parse(raw) as Feedback[];
}

async function load(): Promise<Feedback[]> {
  if (memoryCache) return memoryCache;
  try {
    const raw = await fs.readFile(RUNTIME_PATH, "utf8");
    memoryCache = JSON.parse(raw) as Feedback[];
  } catch {
    memoryCache = await readSeed();
    // Best-effort hydrate of /tmp on first run.
    try {
      await fs.writeFile(RUNTIME_PATH, JSON.stringify(memoryCache, null, 2));
    } catch {
      /* read-only env; in-memory cache is the source of truth */
    }
  }
  return memoryCache;
}

async function save(items: Feedback[]): Promise<void> {
  memoryCache = items;
  try {
    await fs.writeFile(RUNTIME_PATH, JSON.stringify(items, null, 2));
  } catch {
    /* non-writable FS; cache only */
  }
}

function nextId(items: Feedback[]): string {
  const max = items
    .map((i) => Number.parseInt(i.id.replace(/^fb_/, ""), 10))
    .filter((n) => Number.isFinite(n))
    .reduce((a, b) => Math.max(a, b), 0);
  return `fb_${String(max + 1).padStart(3, "0")}`;
}

export async function listFeedback(): Promise<Feedback[]> {
  return [...(await load())];
}

export async function getFeedback(id: string): Promise<Feedback | null> {
  const items = await load();
  return items.find((i) => i.id === id) ?? null;
}

export async function createFeedback(input: NewFeedback): Promise<Feedback> {
  const items = await load();
  const item: Feedback = {
    id: nextId(items),
    createdAt: new Date().toISOString(),
    ...input,
  };
  await save([...items, item]);
  return item;
}

export async function updateFeedback(
  id: string,
  patch: FeedbackPatch,
): Promise<Feedback | null> {
  const items = await load();
  const idx = items.findIndex((i) => i.id === id);
  if (idx === -1) return null;
  const updated = { ...items[idx], ...patch };
  const next = [...items];
  next[idx] = updated;
  await save(next);
  return updated;
}

export async function deleteFeedback(id: string): Promise<boolean> {
  const items = await load();
  const next = items.filter((i) => i.id !== id);
  if (next.length === items.length) return false;
  await save(next);
  return true;
}
