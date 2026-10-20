import { NextResponse } from "next/server";
import { authorized } from "@/lib/auth";
import { db } from "@/lib/db";
export const dynamic = "force-dynamic";
export async function GET() {
  if (!(await authorized()))
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  try {
    const d = await db();
    const [
      subscriptions,
      counts,
      worker,
      lease,
      recent,
      issues,
      hours,
      events,
      control,
    ] = await Promise.all([
      d
        .collection("subscriptions")
        .find(
          {},
          {
            projection: {
              metadata: 1,
              title: 1,
              main_title_override: 1,
              channel: 1,
              enabled: 1,
              checked: 1,
              error: 1,
              active_source: 1,
              source_health: 1,
              available_sources: 1,
              fallback_missing: 1,
              telegram_stats: 1,
              public_url: 1,
            },
          },
        )
        .toArray(),
      d
        .collection("jobs")
        .aggregate([
          {
            $group: {
              _id: { subscription: "$subscription", status: "$status" },
              count: { $sum: 1 },
              latest: { $max: "$sent_at" },
            },
          },
        ])
        .toArray(),
      d.collection("runtime").findOne({ _id: "worker_state" as never }),
      d
        .collection("locks")
        .findOne({ _id: "worker" as never }, { projection: { expires: 1 } }),
      d
        .collection("jobs")
        .find(
          { status: "sent" },
          {
            projection: {
              subscription: 1,
              name: 1,
              number: 1,
              sent_at: 1,
              sent_parts: 1,
              pdf_stats: 1,
            },
          },
        )
        .sort({ sent_at: -1 })
        .limit(20)
        .toArray(),
      d
        .collection("jobs")
        .find(
          {
            status: { $in: ["failed", "uncertain", "processing", "sending"] },
          },
          {
            projection: {
              subscription: 1,
              name: 1,
              number: 1,
              status: 1,
              error: 1,
              attempts: 1,
              preview_receipt: 1,
              delivery_phase: 1,
              started: 1,
            },
          },
        )
        .sort({ started: -1 })
        .limit(100)
        .toArray(),
      d
        .collection("jobs")
        .aggregate([
          {
            $match: {
              status: "sent",
              sent_at: { $gte: new Date(Date.now() - 24 * 3600000) },
            },
          },
          {
            $group: {
              _id: {
                $dateToString: {
                  date: "$sent_at",
                  format: "%Y-%m-%dT%H:00:00Z",
                },
              },
              count: { $sum: 1 },
            },
          },
          { $sort: { _id: 1 } },
        ])
        .toArray(),
      d
        .collection("events")
        .find(
          {},
          {
            projection: {
              at: 1,
              kind: 1,
              subscription: 1,
              number: 1,
              source: 1,
              error_type: 1,
              actor: 1,
            },
          },
        )
        .sort({ at: -1 })
        .limit(60)
        .toArray(),
      d.collection("runtime").findOne({ _id: "publisher_control" as never }),
    ]);
    return NextResponse.json(
      {
        at: new Date(),
        paused: control?.paused === true,
        events: events.map((e) => ({ ...e, _id: String(e._id) })),
        online: !!lease?.expires && lease.expires > new Date(),
        worker: worker
          ? {
              stage: worker.stage,
              host: worker.host,
              chapter_delay: worker.chapter_delay,
              poll_seconds: worker.poll_seconds,
              title: worker.title,
              chapter: worker.chapter,
              job: worker.job,
              page: worker.page,
              pages: worker.pages,
              part: worker.part,
              parts: worker.parts,
              upload_bytes: worker.upload_bytes,
              upload_sent: worker.upload_sent,
              upload_total: worker.upload_total,
              peak_memory_mb: worker.peak_memory_mb,
              database_bytes: worker.database_bytes,
              heartbeat: worker.heartbeat,
              updated: worker.updated,
              error: worker.error,
            }
          : null,
        channels: subscriptions.map((s) => ({
          id: String(s._id),
          title:
            s.main_title_override ||
            s.metadata?.main_title_ru ||
            s.title?.split(" / ")[0],
          enabled: s.enabled,
          checked: s.checked,
          error: s.error,
          source: s.active_source || "MangaShi",
          fallback_missing: s.fallback_missing || [],
          source_health: s.source_health || {},
          available_sources: s.available_sources || [],
          stats: s.telegram_stats || null,
          counts: Object.fromEntries(
            counts
              .filter((c) => c._id.subscription === s._id)
              .map((c) => [c._id.status, c.count]),
          ),
          latest: counts.find(
            (c) => c._id.subscription === s._id && c._id.status === "sent",
          )?.latest,
        })),
        recent: recent.map((j) => ({
          id: String(j._id),
          subscription: j.subscription,
          name: j.name,
          number: String(j.number),
          sent_at: j.sent_at,
          parts: j.sent_parts?.length,
          bytes: j.pdf_stats?.bytes,
        })),
        issues: issues.map((j) => ({
          id: String(j._id),
          subscription: j.subscription,
          name: j.name,
          number: String(j.number),
          status: j.status,
          error: j.error,
          attempts: j.attempts,
          preview: !!j.preview_receipt,
          phase: j.delivery_phase,
        })),
        hours,
      },
      { headers: { "Cache-Control": "private, no-store" } },
    );
  } catch {
    return NextResponse.json(
      { error: "Не удалось связаться с базой данных" },
      { status: 503 },
    );
  }
}
