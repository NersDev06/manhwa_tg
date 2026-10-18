import { NextResponse } from "next/server";
import { authorized } from "@/lib/auth";
import { db } from "@/lib/db";
export async function GET(request: Request) {
  if (!(await authorized()))
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  try {
    const q = new URL(request.url).searchParams;
    const subscription = q.get("channel");
    const status = q.get("status") || "pending";
    if (
      ![
        "pending",
        "sent",
        "failed",
        "uncertain",
        "processing",
        "sending",
      ].includes(status)
    )
      return NextResponse.json({ error: "Invalid status" }, { status: 400 });
    const offset = Math.max(0, Math.min(100000, Number(q.get("offset")) || 0));
    const d = await db();
    const filter = { status, ...(subscription ? { subscription } : {}) };
    const [jobs, total] = await Promise.all([
      d
        .collection("jobs")
        .find(filter, {
          projection: {
            subscription: 1,
            name: 1,
            number: 1,
            status: 1,
            error: 1,
            retry_at: 1,
            attempts: 1,
            sent_at: 1,
            pdf_stats: 1,
          },
        })
        .sort(
          status === "sent"
            ? { sent_at: -1 }
            : { subscription: 1, volume: 1, number: 1 },
        )
        .skip(offset)
        .limit(30)
        .toArray(),
      d.collection("jobs").countDocuments(filter),
    ]);
    return NextResponse.json(
      {
        total,
        jobs: jobs.map((j) => ({
          ...j,
          _id: String(j._id),
          number: String(j.number),
        })),
      },
      { headers: { "Cache-Control": "private, no-store" } },
    );
  } catch {
    return NextResponse.json(
      { error: "Ошибка загрузки очереди" },
      { status: 503 },
    );
  }
}
