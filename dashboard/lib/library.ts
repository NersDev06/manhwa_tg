import "server-only";
import { unstable_cache } from "next/cache";
import { db } from "./db";
import definitions from "@/data/titles.json";
import snapshot from "@/data/library-snapshot.json";
import type { Book, BookSummary, Chapter } from "./library-types";
export const SITE = "https://manhwa-frame.vercel.app";
export const CATALOG = SITE + "/catalog";
export const titles = definitions;
export const jsonLd = (data: unknown) =>
  JSON.stringify(data).replace(/</g, "\\u003c");
export const formatNumber = (n: number) =>
  new Intl.NumberFormat("ru").format(n);
export const date = (value: string | null) =>
  value
    ? new Date(value).toLocaleDateString("ru", {
        day: "numeric",
        month: "long",
        year: "numeric",
        timeZone: "Asia/Bishkek",
      })
    : "уточняется";
export const summarize = (book: Book): BookSummary => {
  const { chapters, ...rest } = book;
  return {
    ...rest,
    count: chapters.length,
    latest: chapters.at(-1)?.number || null,
    latestAt: chapters.at(-1)?.at || null,
  };
};
export const getBooks = unstable_cache(
  async (): Promise<Book[]> => {
    try {
      const d = await db();
      const ids = titles.map((b) => b.subscription);
      const [subs, jobs] = await Promise.all([
        d
          .collection("subscriptions")
          .find({ _id: { $in: ids } as never }, { projection: { checked: 1 } })
          .toArray(),
        d
          .collection("jobs")
          .find(
            { subscription: { $in: ids }, status: "sent" },
            {
              projection: {
                _id: 0,
                subscription: 1,
                number: 1,
                volume: 1,
                sent_parts: 1,
                sent_at: 1,
              },
            },
          )
          .sort({ volume: 1, number: 1 })
          .toArray(),
      ]);
      return titles.map(({ subscription, ...definition }) => {
        const chapters: Chapter[] = jobs
          .filter((j) => j.subscription === subscription)
          .map((j) => ({
            number: String(j.number),
            volume: Number(j.volume),
            at: j.sent_at?.toISOString() || null,
            urls: (j.sent_parts || [])
              .filter(
                (p: { message_id?: number }) =>
                  Number.isSafeInteger(p.message_id) &&
                  Number(p.message_id) > 0,
              )
              .map(
                (p: { message_id: number }) =>
                  definition.channel + "/" + p.message_id,
              ),
          }))
          .filter((c) => c.urls.length > 0);
        const sub = subs.find((s) => String(s._id) === subscription);
        return {
          ...definition,
          chapters,
          checkedAt: sub?.checked?.toISOString() || null,
        };
      });
    } catch {
      // Only verified public chapter links are in this fallback. Private fields never leave the server.
      return titles.map(({ subscription: _, ...definition }) => ({
        ...definition,
        ...snapshot.find((b) => b.slug === definition.slug)!,
      }));
    }
  },
  ["public-library-v1"],
  { revalidate: 300 },
);
export async function getBook(slug: string) {
  return (await getBooks()).find((b) => b.slug === slug);
}
