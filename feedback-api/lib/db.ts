import fs from "fs";
import path from "path";
import { randomUUID } from "crypto";

export type FeedbackCategory = "bug" | "feature" | "general";

export interface Feedback {
  id: string;
  author: string;
  rating: number; // 1–5
  category: FeedbackCategory;
  message: string;
  createdAt: string;
  updatedAt: string;
}

export interface NewFeedback {
  author: string;
  rating: number;
  category: FeedbackCategory;
  message: string;
}

export interface FeedbackFilters {
  author?: string;
  category?: FeedbackCategory;
  rating?: number;
  minRating?: number;
  maxRating?: number;
  limit?: number;
  offset?: number;
}

const DB_PATH = path.join(process.cwd(), "data", "feedback.json");

function readAll(): Feedback[] {
  const raw = fs.readFileSync(DB_PATH, "utf-8");
  return JSON.parse(raw) as Feedback[];
}

function writeAll(items: Feedback[]): void {
  fs.writeFileSync(DB_PATH, JSON.stringify(items, null, 2));
}

export function listFeedback(filters: FeedbackFilters = {}): Feedback[] {
  let items = readAll();

  if (filters.author) {
    items = items.filter((f) => f.author === filters.author);
  }
  if (filters.category) {
    items = items.filter((f) => f.category === filters.category);
  }
  if (filters.rating !== undefined) {
    items = items.filter((f) => f.rating === filters.rating);
  }
  if (filters.minRating !== undefined) {
    items = items.filter((f) => f.rating >= filters.minRating!);
  }
  if (filters.maxRating !== undefined) {
    items = items.filter((f) => f.rating <= filters.maxRating!);
  }

  const offset = filters.offset ?? 0;
  const limit = filters.limit ?? items.length;
  return items.slice(offset, offset + limit);
}

export function getFeedback(id: string): Feedback | undefined {
  return readAll().find((f) => f.id === id);
}

export function createFeedback(data: NewFeedback): Feedback {
  const items = readAll();
  const now = new Date().toISOString();
  const item: Feedback = {
    id: randomUUID(),
    ...data,
    createdAt: now,
    updatedAt: now,
  };
  items.push(item);
  writeAll(items);
  return item;
}

export function updateFeedback(
  id: string,
  patch: Partial<NewFeedback>
): Feedback | undefined {
  const items = readAll();
  const idx = items.findIndex((f) => f.id === id);
  if (idx === -1) return undefined;

  items[idx] = {
    ...items[idx],
    ...patch,
    updatedAt: new Date().toISOString(),
  };
  writeAll(items);
  return items[idx];
}

export function deleteFeedback(id: string): boolean {
  const items = readAll();
  const filtered = items.filter((f) => f.id !== id);
  if (filtered.length === items.length) return false;
  writeAll(filtered);
  return true;
}

export interface FeedbackSummary {
  total: number;
  averageRating: number;
  byCategory: Record<string, number>;
  byRating: Record<number, number>;
}

export function summarizeFeedback(): FeedbackSummary {
  const items = readAll();
  const total = items.length;
  const averageRating =
    total === 0 ? 0 : items.reduce((s, f) => s + f.rating, 0) / total;

  const byCategory: Record<string, number> = {};
  const byRating: Record<number, number> = {};

  for (const f of items) {
    byCategory[f.category] = (byCategory[f.category] ?? 0) + 1;
    byRating[f.rating] = (byRating[f.rating] ?? 0) + 1;
  }

  return {
    total,
    averageRating: Math.round(averageRating * 100) / 100,
    byCategory,
    byRating,
  };
}
