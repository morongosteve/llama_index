import { NextRequest, NextResponse } from "next/server";
import { getById, update, remove } from "@/lib/db";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const item = getById(id);
  if (!item) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  return NextResponse.json(item);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const patch = body as Record<string, unknown>;
  const allowed = ["text", "rating", "category", "author", "tags"];
  const sanitized: Record<string, unknown> = {};

  for (const key of allowed) {
    if (key in patch) {
      sanitized[key] = patch[key];
    }
  }

  if ("rating" in sanitized) {
    const r = sanitized.rating as number;
    if (typeof r !== "number" || r < 1 || r > 5 || !Number.isInteger(r)) {
      return NextResponse.json({ error: "rating must be an integer 1-5" }, { status: 400 });
    }
  }

  const updated = update(id, sanitized);
  if (!updated) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  return NextResponse.json(updated);
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const removed = remove(id);
  if (!removed) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  return NextResponse.json({ deleted: true });
}
