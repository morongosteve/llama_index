import { NextRequest, NextResponse } from "next/server";
import { getAll, create } from "@/lib/db";

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;

  const filters = {
    category: params.get("category") ?? undefined,
    rating: params.has("rating") ? Number(params.get("rating")) : undefined,
    minRating: params.has("minRating") ? Number(params.get("minRating")) : undefined,
    maxRating: params.has("maxRating") ? Number(params.get("maxRating")) : undefined,
    tag: params.get("tag") ?? undefined,
    author: params.get("author") ?? undefined,
    sort: (params.get("sort") as "newest" | "oldest" | "rating-asc" | "rating-desc") ?? undefined,
    limit: params.has("limit") ? Number(params.get("limit")) : undefined,
    offset: params.has("offset") ? Number(params.get("offset")) : undefined,
  };

  const result = getAll(filters);
  return NextResponse.json(result);
}

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { text, rating, category, author, tags } = body as Record<string, unknown>;

  if (typeof text !== "string" || !text.trim()) {
    return NextResponse.json({ error: "text is required" }, { status: 400 });
  }
  if (typeof rating !== "number" || rating < 1 || rating > 5 || !Number.isInteger(rating)) {
    return NextResponse.json({ error: "rating must be an integer 1-5" }, { status: 400 });
  }
  if (typeof category !== "string" || !category.trim()) {
    return NextResponse.json({ error: "category is required" }, { status: 400 });
  }
  if (typeof author !== "string" || !author.trim()) {
    return NextResponse.json({ error: "author is required" }, { status: 400 });
  }
  if (!Array.isArray(tags) || !tags.every((t) => typeof t === "string")) {
    return NextResponse.json({ error: "tags must be an array of strings" }, { status: 400 });
  }

  const entry = create({
    text: text.trim(),
    rating,
    category: category.trim(),
    author: author.trim(),
    tags,
  });

  return NextResponse.json(entry, { status: 201 });
}
