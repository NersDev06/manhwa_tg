import { NextResponse } from "next/server";
import { authorized, sameOrigin } from "@/lib/auth";
import { db } from "@/lib/db";
export async function POST(request: Request) {
  if (!(await authorized()))
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!sameOrigin(request))
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  let body;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Неверный запрос" }, { status: 400 });
  }
  if (
    typeof body?.paused !== "boolean" ||
    (body.subscription !== undefined &&
      (typeof body.subscription !== "string" ||
        !/^[a-f0-9]{20}$/.test(body.subscription)))
  )
    return NextResponse.json({ error: "Неверные параметры" }, { status: 400 });
  try {
    const d = await db();
    const at = new Date();
    if (body.subscription) {
      const result = await d
        .collection("subscriptions")
        .updateOne(
          { _id: body.subscription as never },
          { $set: { enabled: !body.paused } },
        );
      if (!result.matchedCount)
        return NextResponse.json({ error: "Канал не найден" }, { status: 404 });
    } else {
      await d
        .collection("runtime")
        .updateOne(
          { _id: "publisher_control" as never },
          { $set: { paused: body.paused, updated: at } },
          { upsert: true },
        );
    }
    await d
      .collection("events")
      .insertOne({
        at,
        kind: body.paused ? "paused" : "resumed",
        subscription: body.subscription || null,
        actor: "dashboard",
      });
    return NextResponse.json({ ok: true, paused: body.paused });
  } catch {
    return NextResponse.json(
      { error: "Не удалось сохранить настройку" },
      { status: 503 },
    );
  }
}
