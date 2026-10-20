import type { MetadataRoute } from "next";
import { CATALOG, getBooks } from "@/lib/library";
export const revalidate = 3600;
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const books = await getBooks();
  return [
    {
      url: CATALOG,
      lastModified:
        books
          .map((b) => b.chapters.at(-1)?.at || "")
          .sort()
          .at(-1) || undefined,
    },
    { url: CATALOG + "/guide" },
    ...books.map((b) => ({
      url: CATALOG + "/" + b.slug,
      lastModified: b.chapters.at(-1)?.at || undefined,
    })),
  ];
}
