import { NextRequest, NextResponse } from "next/server";
import { getById, update, remove } from "@/lib/db";
import { validateApiKey } from "@/lib/auth";

// GET /api/feedback/:id — public, no auth required
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const feedback = getById(id);

    if (!feedback) {
      return NextResponse.json(
        { error: "Feedback not found" },
        { status: 404 }
      );
    }

    return NextResponse.json(feedback);
  } catch (error) {
    console.error("GET /api/feedback/[id] error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}

// PATCH /api/feedback/:id — requires auth
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!validateApiKey(request)) {
    return NextResponse.json(
      { error: "Invalid or missing API key" },
      { status: 401 }
    );
  }

  try {
    const { id } = await params;
    const body = await request.json();

    // Validate optional fields if provided
    if (body.rating !== undefined) {
      if (typeof body.rating !== "number" || body.rating < 1 || body.rating > 5) {
        return NextResponse.json(
          { error: "rating must be a number between 1 and 5" },
          { status: 400 }
        );
      }
    }

    if (body.tags !== undefined && !Array.isArray(body.tags)) {
      return NextResponse.json(
        { error: "tags must be an array of strings" },
        { status: 400 }
      );
    }

    const feedback = update(id, body);

    if (!feedback) {
      return NextResponse.json(
        { error: "Feedback not found" },
        { status: 404 }
      );
    }

    return NextResponse.json(feedback);
  } catch (error) {
    console.error("PATCH /api/feedback/[id] error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}

// DELETE /api/feedback/:id — requires auth
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!validateApiKey(request)) {
    return NextResponse.json(
      { error: "Invalid or missing API key" },
      { status: 401 }
    );
  }

  try {
    const { id } = await params;
    const deleted = remove(id);

    if (!deleted) {
      return NextResponse.json(
        { error: "Feedback not found" },
        { status: 404 }
      );
    }

    return NextResponse.json({ message: "Feedback deleted successfully" });
  } catch (error) {
    console.error("DELETE /api/feedback/[id] error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
