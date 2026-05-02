import { NextResponse } from "next/server";
import { listFeedback } from "@/lib/store";
import { Category, Sentiment } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  const items = await listFeedback();
  const total = items.length;

  const bySentiment: Record<Sentiment, number> = { positive: 0, neutral: 0, negative: 0 };
  const byCategory: Record<Category, number> = {
    bug: 0,
    feature: 0,
    praise: 0,
    question: 0,
    other: 0,
  };
  let ratingSum = 0;
  let latest: string | null = null;

  for (const i of items) {
    bySentiment[i.sentiment] += 1;
    byCategory[i.category] += 1;
    ratingSum += i.rating;
    if (!latest || i.createdAt > latest) latest = i.createdAt;
  }

  const averageRating = total > 0 ? Number((ratingSum / total).toFixed(2)) : 0;

  return NextResponse.json({
    total,
    averageRating,
    bySentiment,
    byCategory,
    latestCreatedAt: latest,
  });
}
