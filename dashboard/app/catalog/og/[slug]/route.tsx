import { ImageResponse } from "next/og";
import titles from "@/data/titles.json";
export const runtime = "nodejs";
export const revalidate = 86400;
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ slug: string }> },
) {
  const { slug } = await params;
  const book = titles.find((b) => b.slug === slug);
  if (slug !== "library" && !book)
    return new Response("Not found", { status: 404 });
  const heading = book?.title || "Найди свою следующую манхву";
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#172b22",
          color: "#f2f0e7",
          padding: "60px 72px",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: 26,
            letterSpacing: 5,
            color: "#bad4ab",
          }}
        >
          <span>FRAME</span>
          <span>БИБЛИОТЕКА МАНХВЫ</span>
        </div>
        <div
          style={{
            display: "flex",
            fontSize: heading.length > 35 ? 62 : 82,
            lineHeight: 1.1,
            maxWidth: 980,
          }}
        >
          {heading}
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: 25,
            color: "#c3cdbf",
          }}
        >
          <span>
            {book?.genres.join(" · ") || "Описания · Оглавления · Telegram"}
          </span>
          <span>НА РУССКОМ ↗</span>
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
      headers: { "Cache-Control": "public, max-age=86400" },
    },
  );
}
