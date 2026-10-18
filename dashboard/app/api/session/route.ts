import { NextResponse } from "next/server";
import { equal, token, sameOrigin } from "@/lib/auth";
import { db } from "@/lib/db";
import { createHash } from "node:crypto";
export async function POST(request: Request) {
  if (!sameOrigin(request))
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  try {
    const key = createHash("sha256")
      .update(request.headers.get("x-forwarded-for")?.split(",")[0] || "local")
      .digest("hex");
    const database = await db();
    const attempt = await database
      .collection("dashboard_login")
      .findOneAndUpdate(
        { _id: key as never },
        {
          $inc: { attempts: 1 },
          $setOnInsert: { expires: new Date(Date.now() + 900000) },
        },
        { upsert: true, returnDocument: "after" },
      );
    if (attempt && attempt.expires < new Date()) {
      await database
        .collection("dashboard_login")
        .updateOne(
          { _id: key as never },
          { $set: { attempts: 1, expires: new Date(Date.now() + 900000) } },
        );
    } else if ((attempt?.attempts || 0) > 15)
      return NextResponse.json(
        { error: "Слишком много попыток. Повтори через 15 минут." },
        { status: 429 },
      );
    const body = await request.json();
    const password = process.env.DASHBOARD_PASSWORD;
    if (
      !password ||
      typeof body.password !== "string" ||
      !equal(body.password, password)
    )
      return NextResponse.json({ error: "Неверный пароль" }, { status: 401 });
    const response = NextResponse.json({ ok: true });
    response.cookies.set("manhwa_session", token(), {
      httpOnly: true,
      secure: new URL(request.url).protocol === "https:",
      sameSite: "strict",
      maxAge: 604800,
      path: "/",
    });
    return response;
  } catch {
    return NextResponse.json(
      { error: "Сервис временно недоступен" },
      { status: 503 },
    );
  }
}
export async function DELETE(request: Request) {
  if (!sameOrigin(request))
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  const response = NextResponse.json({ ok: true });
  response.cookies.delete("manhwa_session");
  return response;
}
