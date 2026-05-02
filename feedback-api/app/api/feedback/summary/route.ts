import { NextResponse } from "next/server";
import { summarizeFeedback } from "@/lib/db";

// GET /api/feedback/summary
// Returns aggregate stats: total, averageRating, breakdown by category and rating
export async function GET() {
  const summary = summarizeFeedback();
  return NextResponse.json({ data: summary });
}
