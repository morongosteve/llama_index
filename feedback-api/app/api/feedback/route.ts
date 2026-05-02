import { NextRequest, NextResponse } from "next/server";
import {
  listFeedback,
  createFeedback,
  FeedbackFilters,
  FeedbackCategory,
} from "@/lib/db";

// GET /api/feedback
// Query params: author, category, rating, minRating, maxRating, limit, offset
export async function GET(req: NextRequest) {
  const p = req.nextUrl.searchParams;

  const filters: FeedbackFilters = {};
  if (p.has("author")) filters.author = p.get("author")!;
  if (p.has("category"))
    filters.category = p.get("category") as FeedbackCategory;
  if (p.has("rating")) filters.rating = parseInt(p.get("rating")!, 10);
  if (p.has("minRating")) filters.minRating = parseInt(p.get("minRating")!, 10);
  if (p.has("maxRating")) filters.maxRating = parseInt(p.get("maxRating")!, 10);
  if (p.has("limit")) filters.limit = parseInt(p.get("limit")!, 10);
  if (p.has("offset")) filters.offset = parseInt(p.get("offset")!, 10);

  const items = listFeedback(filters);
  return NextResponse.json({ data: items, count: items.length });
}

// POST /api/feedback
// Body: { author, rating, category, message }
export async function POST(req: NextRequest) {
  const body = await req.json();
  const { author, rating, category, message } = body;

  if (!author || !rating || !category || !message) {
    return NextResponse.json(
      { error: "author, rating, category, and message are required" },
      { status: 400 }
    );
  }
  if (rating < 1 || rating > 5 || !Number.isInteger(rating)) {
    return NextResponse.json(
      { error: "rating must be an integer between 1 and 5" },
      { status: 400 }
    );
  }
  if (!["bug", "feature", "general"].includes(category)) {
    return NextResponse.json(
      { error: "category must be one of: bug, feature, general" },
      { status: 400 }
    );
  }

  const item = createFeedback({ author, rating, category, message });
  return NextResponse.json({ data: item }, { status: 201 });
}
