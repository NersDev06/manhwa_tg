import { chaptersLabel } from "@/lib/wording";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowUpRight,
  ArrowDown,
  BookOpen,
  ChevronRight,
  Clock3,
} from "lucide-react";
import ChapterDirectory from "@/components/chapter-directory";
import {
  getBook,
  getBooks,
  titles,
  CATALOG,
  jsonLd,
  date,
} from "@/lib/library";
export const revalidate = 300;
export function generateStaticParams() {
  return titles.map((b) => ({ slug: b.slug }));
}
export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const b = await getBook((await params).slug);
  if (!b) return { title: "Произведение не найдено", robots: { index: false } };
  return {
    title: `${b.title} — главы на русском`,
    description: b.description + " Оглавление и Telegram-канал.",
    alternates: { canonical: CATALOG + "/" + b.slug },
    openGraph: {
      title: b.title + " — FRAME",
      description: b.description,
      url: CATALOG + "/" + b.slug,
      type: "website",
      locale: "ru_RU",
      images: [{ url: CATALOG + "/og/" + b.slug, width: 1200, height: 630 }],
    },
    twitter: {
      card: "summary_large_image",
      images: [CATALOG + "/og/" + b.slug],
    },
  };
}
export default async function BookPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const b = await getBook((await params).slug);
  if (!b) notFound();
  const first = b.chapters[0],
    last = b.chapters.at(-1);
  const related = (await getBooks())
    .filter((x) => x.slug !== b.slug)
    .map((x) => ({
      book: x,
      score: x.genres.filter((g) => b.genres.includes(g)).length,
    }))
    .sort((a, z) => z.score - a.score)
    .slice(0, 3)
    .map((x) => x.book);
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: jsonLd([
            {
              "@context": "https://schema.org",
              "@type": "BreadcrumbList",
              itemListElement: [
                {
                  "@type": "ListItem",
                  position: 1,
                  name: "Каталог манхвы",
                  item: CATALOG,
                },
                {
                  "@type": "ListItem",
                  position: 2,
                  name: b.title,
                  item: CATALOG + "/" + b.slug,
                },
              ],
            },
            {
              "@context": "https://schema.org",
              "@type": "WebPage",
              name: b.title + " — главы на русском",
              url: CATALOG + "/" + b.slug,
              description: b.description,
              about: {
                "@type": "Book",
                name: b.title,
                alternateName: [b.english, ...b.aliases],
                genre: b.genres,
                image: new URL(b.cover, CATALOG).href,
                sameAs: b.reference,
              },
            },
          ]),
        }}
      />
      <nav className="lib-breadcrumb" aria-label="Хлебные крошки">
        <Link href="/catalog">Каталог</Link>
        <ChevronRight size={13} />
        <span>{b.title}</span>
      </nav>
      <section
        className="lib-detail-hero"
        style={{ "--book-tone": b.tone } as React.CSSProperties}
      >
        <div className="lib-detail-art">
          <div className="lib-detail-book">
            <img
              src={b.cover}
              alt={"Обложка «" + b.title + "»"}
              width={b.coverWidth}
              height={b.coverHeight}
              fetchPriority="high"
            />
          </div>
          <span>FRAME / БИБЛИОТЕКА</span>
        </div>
        <div className="lib-detail-copy">
          <div className="lib-tags">
            {b.genres.map((g) => (
              <span key={g}>{g}</span>
            ))}
          </div>
          <h1>{b.title}</h1>
          <p className="lib-english">{b.english}</p>
          <p className="lib-detail-lead">{b.description}</p>
          <div className="lib-detail-actions">
            {first && (
              <a
                href={first.urls[0]}
                target="_blank"
                rel="noopener noreferrer"
                className="lib-button"
              >
                Читать с начала <ArrowUpRight size={17} />
              </a>
            )}
            <a href="#chapters" className="lib-outline">
              Оглавление <ArrowDown size={16} />
            </a>
          </div>
          <div className="lib-detail-facts">
            <span>
              <BookOpen size={17} />
              {chaptersLabel(b.chapters.length)} в канале
            </span>
            <span>
              <Clock3 size={17} />
              Проверяем раз в час
            </span>
          </div>
          {last && (
            <a
              className="lib-latest"
              href={last.urls[0]}
              target="_blank"
              rel="noopener noreferrer"
            >
              <span>
                Последняя публикация<strong>Глава {last.number}</strong>
              </span>
              <span>
                {date(last.at)}
                <ArrowUpRight size={18} />
              </span>
            </a>
          )}
        </div>
      </section>
      <section className="lib-about">
        <div>
          <span className="lib-kicker">ОБ ЭТОЙ ИСТОРИИ</span>
          <h2>Почему стоит открыть</h2>
        </div>
        <div>
          <p>{b.about}</p>
          <p>
            В оглавлении ниже собраны опубликованные главы на русском. Можно
            начать сначала или перейти прямо к нужному номеру. Если глава
            разделена на несколько файлов, рядом указаны все части.
          </p>
          <details className="lib-aliases">
            <summary>Другие названия этой манхвы</summary>
            <p>{Array.from(new Set([b.english, ...b.aliases])).join(" · ")}</p>
          </details>
          <a
            href={b.reference}
            className="lib-reference"
            target="_blank"
            rel="noopener noreferrer"
          >
            Страница произведения у издателя <ArrowUpRight size={13} />
          </a>
        </div>
      </section>
      <ChapterDirectory slug={b.slug} chapters={b.chapters} />
      <section className="lib-channel-callout">
        <div>
          <span className="lib-kicker">ПРОДОЛЖЕНИЕ — В КАНАЛЕ</span>
          <h2>
            Следующая глава
            <br />
            может быть совсем близко.
          </h2>
          <p>
            Подпишись на «{b.title}», чтобы возвращаться к новым публикациям.
          </p>
        </div>
        <a
          href={b.channel}
          className="lib-button"
          target="_blank"
          rel="noopener noreferrer"
        >
          Открыть Telegram-канал <ArrowUpRight size={18} />
        </a>
      </section>
      <section className="lib-related">
        <div className="lib-section-heading">
          <div>
            <span className="lib-kicker">РЯДОМ НА ПОЛКЕ</span>
            <h2>Что почитать дальше</h2>
          </div>
          <Link href="/catalog" className="lib-text-link">
            Весь каталог <ArrowUpRight size={16} />
          </Link>
        </div>
        <div className="lib-related-grid">
          {related.map((x) => (
            <Link href={"/catalog/" + x.slug} key={x.slug}>
              <img
                src={x.cover}
                alt={"Обложка «" + x.title + "»"}
                width={100}
                height={140}
                loading="lazy"
              />
              <div>
                <small>{x.genres.slice(0, 2).join(" / ")}</small>
                <h3>{x.title}</h3>
                <span>
                  {chaptersLabel(x.chapters.length)} <ArrowUpRight size={15} />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
