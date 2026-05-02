import { NextResponse } from "next/server";
import { getSummary } from "@/lib/db";

export async function GET() {
  const summary = getSummary();
  return NextResponse.json(summary);
}
