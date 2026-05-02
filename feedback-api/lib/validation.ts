import { Category, NewFeedback, Sentiment, FeedbackPatch } from "./types";

const SENTIMENTS: Sentiment[] = ["positive", "neutral", "negative"];
const CATEGORIES: Category[] = ["bug", "feature", "praise", "question", "other"];

export type ValidationResult<T> =
  | { ok: true; value: T }
  | { ok: false; error: string };

function isString(v: unknown): v is string {
  return typeof v === "string" && v.length > 0;
}

export function parseNewFeedback(body: unknown): ValidationResult<NewFeedback> {
  if (!body || typeof body !== "object") return { ok: false, error: "Body must be an object" };
  const b = body as Record<string, unknown>;

  if (!isString(b.message)) return { ok: false, error: "message is required (non-empty string)" };
  if (!isString(b.user)) return { ok: false, error: "user is required (non-empty string)" };
  if (typeof b.rating !== "number" || b.rating < 1 || b.rating > 5)
    return { ok: false, error: "rating must be a number 1-5" };
  if (!SENTIMENTS.includes(b.sentiment as Sentiment))
    return { ok: false, error: `sentiment must be one of ${SENTIMENTS.join(", ")}` };
  if (!CATEGORIES.includes(b.category as Category))
    return { ok: false, error: `category must be one of ${CATEGORIES.join(", ")}` };

  return {
    ok: true,
    value: {
      message: b.message,
      user: b.user,
      rating: b.rating,
      sentiment: b.sentiment as Sentiment,
      category: b.category as Category,
    },
  };
}

export function parseFeedbackPatch(body: unknown): ValidationResult<FeedbackPatch> {
  if (!body || typeof body !== "object") return { ok: false, error: "Body must be an object" };
  const b = body as Record<string, unknown>;
  const out: FeedbackPatch = {};

  if (b.message !== undefined) {
    if (!isString(b.message)) return { ok: false, error: "message must be a non-empty string" };
    out.message = b.message;
  }
  if (b.user !== undefined) {
    if (!isString(b.user)) return { ok: false, error: "user must be a non-empty string" };
    out.user = b.user;
  }
  if (b.rating !== undefined) {
    if (typeof b.rating !== "number" || b.rating < 1 || b.rating > 5)
      return { ok: false, error: "rating must be a number 1-5" };
    out.rating = b.rating;
  }
  if (b.sentiment !== undefined) {
    if (!SENTIMENTS.includes(b.sentiment as Sentiment))
      return { ok: false, error: `sentiment must be one of ${SENTIMENTS.join(", ")}` };
    out.sentiment = b.sentiment as Sentiment;
  }
  if (b.category !== undefined) {
    if (!CATEGORIES.includes(b.category as Category))
      return { ok: false, error: `category must be one of ${CATEGORIES.join(", ")}` };
    out.category = b.category as Category;
  }

  return { ok: true, value: out };
}
