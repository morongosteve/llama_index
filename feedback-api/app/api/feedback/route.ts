import { NextRequest, NextResponse } from "next/server";
import { createFeedback, listFeedback } from "@/lib/store";
import { parseNewFeedback } from "@/lib/validation";
import { Category, Feedback, Sentiment } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const category = searchParams.get("category");
  const sentiment = searchParams.get("sentiment");
  const user = searchParams.get("user");
  const minRating = numParam(searchParams.get("minRating"));
  const maxRating = numParam(searchParams.get("maxRating"));
  const search = searchParams.get("q")?.toLowerCase();
  const limit = numParam(searchParams.get("limit"));

  let items: Feedback[] = await listFeedback();

  if (category) items = items.filter((i) => i.category === (category as Category));
  if (sentiment) items = items.filter((i) => i.sentiment === (sentiment as Sentiment));
  if (user) items = items.filter((i) => i.user === user);
  if (minRating !== null) items = items.filter((i) => i.rating >= minRating);
  if (maxRating !== null) items = items.filter((i) => i.rating <= maxRating);
  if (search) items = items.filter((i) => i.message.toLowerCase().includes(search));

  items.sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
  if (limit !== null) items = items.slice(0, limit);

  return NextResponse.json({ count: items.length, items });
}

export async function POST(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const parsed = parseNewFeedback(body);
  if (!parsed.ok) return NextResponse.json({ error: parsed.error }, { status: 400 });
  const created = await createFeedback(parsed.value);
  return NextResponse.json(created, { status: 201 });
}

function numParam(v: string | null): number | null {
  if (v === null) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
