import { NextRequest, NextResponse } from "next/server";
import { getFeedback, updateFeedback, deleteFeedback, FeedbackCategory } from "@/lib/db";

// GET /api/feedback/:id
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const item = getFeedback(id);
  if (!item) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  return NextResponse.json({ data: item });
}

// PUT /api/feedback/:id
// Body: partial { author, rating, category, message }
export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await req.json();
  const { author, rating, category, message } = body;

  if (rating !== undefined) {
    if (rating < 1 || rating > 5 || !Number.isInteger(rating)) {
      return NextResponse.json(
        { error: "rating must be an integer between 1 and 5" },
        { status: 400 }
      );
    }
  }
  if (category !== undefined && !["bug", "feature", "general"].includes(category)) {
    return NextResponse.json(
      { error: "category must be one of: bug, feature, general" },
      { status: 400 }
    );
  }

  const patch: Partial<{ author: string; rating: number; category: FeedbackCategory; message: string }> = {};
  if (author !== undefined) patch.author = author;
  if (rating !== undefined) patch.rating = rating;
  if (category !== undefined) patch.category = category as FeedbackCategory;
  if (message !== undefined) patch.message = message;

  const updated = updateFeedback(id, patch);
  if (!updated) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  return NextResponse.json({ data: updated });
}

// DELETE /api/feedback/:id
export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const deleted = deleteFeedback(id);
  if (!deleted) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  return NextResponse.json({ data: { deleted: true, id } });
}
