import { NextRequest, NextResponse } from "next/server";
import { getAll, create, type FeedbackQuery } from "@/lib/db";
import { validateApiKey } from "@/lib/auth";

// GET /api/feedback — public, no auth required
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);

    const query: FeedbackQuery = {
      category: searchParams.get("category") || undefined,
      rating: searchParams.get("rating") || undefined,
      minRating: searchParams.get("minRating") || undefined,
      maxRating: searchParams.get("maxRating") || undefined,
      tag: searchParams.get("tag") || undefined,
      author: searchParams.get("author") || undefined,
      sort: (searchParams.get("sort") as FeedbackQuery["sort"]) || undefined,
      limit: searchParams.get("limit") || undefined,
      offset: searchParams.get("offset") || undefined,
    };

    const result = getAll(query);
    return NextResponse.json(result);
  } catch (error) {
    console.error("GET /api/feedback error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}

// POST /api/feedback — requires auth
export async function POST(request: NextRequest) {
  if (!validateApiKey(request)) {
    return NextResponse.json(
      { error: "Invalid or missing API key" },
      { status: 401 }
    );
  }

  try {
    const body = await request.json();

    // Validate required fields
    const { text, rating, category, author, tags } = body;

    if (!text || typeof text !== "string") {
      return NextResponse.json(
        { error: "text is required and must be a string" },
        { status: 400 }
      );
    }

    if (!rating || typeof rating !== "number" || rating < 1 || rating > 5) {
      return NextResponse.json(
        { error: "rating is required and must be a number between 1 and 5" },
        { status: 400 }
      );
    }

    if (!category || typeof category !== "string") {
      return NextResponse.json(
        { error: "category is required and must be a string" },
        { status: 400 }
      );
    }

    if (!author || typeof author !== "string") {
      return NextResponse.json(
        { error: "author is required and must be a string" },
        { status: 400 }
      );
    }

    if (!Array.isArray(tags)) {
      return NextResponse.json(
        { error: "tags is required and must be an array of strings" },
        { status: 400 }
      );
    }

    const feedback = create({ text, rating, category, author, tags });
    return NextResponse.json(feedback, { status: 201 });
  } catch (error) {
    console.error("POST /api/feedback error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
