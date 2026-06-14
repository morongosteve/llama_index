import { NextResponse } from "next/server";
import { getSummary } from "@/lib/db";

// GET /api/feedback/summary — public, no auth required
export async function GET() {
  try {
    const summary = getSummary();
    return NextResponse.json(summary);
  } catch (error) {
    console.error("GET /api/feedback/summary error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
