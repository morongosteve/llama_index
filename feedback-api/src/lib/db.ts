import fs from "fs";
import path from "path";
import crypto from "crypto";

export interface Feedback {
  id: string;
  text: string;
  rating: number;
  category: string;
  author: string;
  createdAt: string;
  tags: string[];
}

const DB_PATH = path.join(process.cwd(), "data", "feedback.json");

function read(): Feedback[] {
  const raw = fs.readFileSync(DB_PATH, "utf-8");
  return JSON.parse(raw);
}

function write(data: Feedback[]): void {
  fs.writeFileSync(DB_PATH, JSON.stringify(data, null, 2));
}

export function getAll(filters?: {
  category?: string;
  rating?: number;
  minRating?: number;
  maxRating?: number;
  tag?: string;
  author?: string;
  sort?: "newest" | "oldest" | "rating-asc" | "rating-desc";
  limit?: number;
  offset?: number;
}): { items: Feedback[]; total: number } {
  let items = read();

  if (filters?.category) {
    items = items.filter((f) => f.category === filters.category);
  }
  if (filters?.rating !== undefined) {
    items = items.filter((f) => f.rating === filters.rating);
  }
  if (filters?.minRating !== undefined) {
    items = items.filter((f) => f.rating >= filters.minRating!);
  }
  if (filters?.maxRating !== undefined) {
    items = items.filter((f) => f.rating <= filters.maxRating!);
  }
  if (filters?.tag) {
    items = items.filter((f) => f.tags.includes(filters.tag!));
  }
  if (filters?.author) {
    items = items.filter((f) => f.author === filters.author);
  }

  const total = items.length;

  switch (filters?.sort) {
    case "newest":
      items.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
      break;
    case "oldest":
      items.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
      break;
    case "rating-asc":
      items.sort((a, b) => a.rating - b.rating);
      break;
    case "rating-desc":
      items.sort((a, b) => b.rating - a.rating);
      break;
    default:
      items.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  }

  const offset = filters?.offset ?? 0;
  const limit = filters?.limit ?? items.length;
  items = items.slice(offset, offset + limit);

  return { items, total };
}

export function getById(id: string): Feedback | undefined {
  return read().find((f) => f.id === id);
}

export function create(
  input: Omit<Feedback, "id" | "createdAt">
): Feedback {
  const items = read();
  const entry: Feedback = {
    ...input,
    id: `fb_${crypto.randomBytes(6).toString("hex")}`,
    createdAt: new Date().toISOString(),
  };
  items.push(entry);
  write(items);
  return entry;
}

export function update(
  id: string,
  patch: Partial<Omit<Feedback, "id" | "createdAt">>
): Feedback | null {
  const items = read();
  const idx = items.findIndex((f) => f.id === id);
  if (idx === -1) return null;
  items[idx] = { ...items[idx], ...patch };
  write(items);
  return items[idx];
}

export function remove(id: string): boolean {
  const items = read();
  const filtered = items.filter((f) => f.id !== id);
  if (filtered.length === items.length) return false;
  write(filtered);
  return true;
}

export function getSummary(): {
  totalCount: number;
  averageRating: number;
  ratingDistribution: Record<number, number>;
  categoryCounts: Record<string, number>;
  topTags: { tag: string; count: number }[];
  recentCount7d: number;
} {
  const items = read();
  const now = Date.now();
  const sevenDaysAgo = now - 7 * 24 * 60 * 60 * 1000;

  const ratingDistribution: Record<number, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
  const categoryCounts: Record<string, number> = {};
  const tagCounts: Record<string, number> = {};
  let ratingSum = 0;
  let recentCount = 0;

  for (const item of items) {
    ratingSum += item.rating;
    ratingDistribution[item.rating] = (ratingDistribution[item.rating] || 0) + 1;
    categoryCounts[item.category] = (categoryCounts[item.category] || 0) + 1;
    for (const tag of item.tags) {
      tagCounts[tag] = (tagCounts[tag] || 0) + 1;
    }
    if (new Date(item.createdAt).getTime() > sevenDaysAgo) {
      recentCount++;
    }
  }

  const topTags = Object.entries(tagCounts)
    .map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);

  return {
    totalCount: items.length,
    averageRating: items.length > 0 ? Math.round((ratingSum / items.length) * 100) / 100 : 0,
    ratingDistribution,
    categoryCounts,
    topTags,
    recentCount7d: recentCount,
  };
}
