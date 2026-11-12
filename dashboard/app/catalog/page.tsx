import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowDown,
  ArrowUpRight,
  BookOpen,
  Clock3,
  ListTree,
} from "lucide-react";
import LibraryExplorer from "@/components/library-explorer";
import {
  CATALOG,
  getBooks,
  summarize,
  jsonLd,
  formatNumber,
} from "@/lib/library";
export const revalidate = 300;
export const metadata: Metadata = {
  title: { absolute: "Манхва на русском — каталог Telegram-каналов | FRAME" },
  description: "Восемь произведений манхвы на русском языке с полными оглавлениями и прямыми ссылками на главы в Telegram. Фэнтези, экшен, романтика.",
  keywords: ["манхва", "манхва на русском", "читать манхву", "telegram манхва", "корейские комиксы", "webtoon"],
  alternates: { canonical: CATALOG },
  openGraph: {
    title: "FRAME — найди свою следующую манхву",
    description:
      "Восемь историй, оглавления и прямые ссылки на главы на русском.",
    url: CATALOG,
    type: "website",
    locale: "ru_RU",
    siteName: "FRAME",
    images: [{ url: CATALOG + "/og/library", width: 1200, height: 630, alt: "Каталог манхвы FRAME" }],
  },
  twitter: { 
    card: "summary_large_image", 
    images: [CATALOG + "/og/library"],
    site: "@manhwa_frame",
  },
};
export default async function CatalogPage() {
  const books = await getBooks(),
    total = books.reduce((n, b) => n + b.chapters.length, 0);
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: jsonLd({
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            name: "FRAME — каталог манхвы на русском",
            url: CATALOG,
            mainEntity: {
              "@type": "ItemList",
              itemListElement: books.map((b, i) => ({
                "@type": "ListItem",
                position: i + 1,
                url: CATALOG + "/" + b.slug,
                name: b.title,
              })),
            },
          }),
        }}
      />
      <section className="lib-hero">
        <div className="lib-hero-copy">
          <span className="lib-kicker">ВОСЕМЬ МИРОВ. ОДНА ПОЛКА.</span>
          <h1>
            История найдётся.
            <br />
            <em>Осталось открыть.</em>
          </h1>
          <p>
            Манхва на русском — от уютной фермы в башне до второго шанса на поле
            боя. Выбирай историю, находи нужную главу и читай в Telegram.
          </p>
          <div className="lib-hero-actions">
            <a href="#titles" className="lib-button">
              Выбрать манхву <ArrowDown size={17} />
            </a>
            <Link href="/catalog/guide" className="lib-text-link">
              Как здесь всё устроено <ArrowUpRight size={16} />
            </Link>
          </div>
          <div className="lib-hero-numbers">
            <span>
              <strong>{books.length}</strong> произведений
            </span>
            <span>
              <strong>{formatNumber(total)}</strong> опубликованных глав
            </span>
          </div>
        </div>
        <div className="lib-hero-art" aria-hidden="true">
          <div className="lib-orbit" />
          <div className="lib-shelf-line" />
          {[books[5], books[0], books[2]].map((b, i) => (
            <div className={"lib-hero-book hb-" + i} key={b.slug}>
              <img
                src={b.cover}
                alt=""
                width={b.coverWidth}
                height={b.coverHeight}
              />
              <span>FRAME / {String(i + 1).padStart(2, "0")}</span>
            </div>
          ))}
          <span className="lib-art-label">ОТКРОЙ СВОЮ СЛЕДУЮЩУЮ</span>
        </div>
      </section>
      <section className="lib-promise" aria-label="О каталоге">
        <span>
          <BookOpen size={20} />
          <strong>Главы по порядку</strong>
          <small>С прямыми ссылками на посты</small>
        </span>
        <span>
          <ListTree size={20} />
          <strong>Нужное название найдётся</strong>
          <small>На русском и английском</small>
        </span>
        <span>
          <Clock3 size={20} />
          <strong>Следим за продолжением</strong>
          <small>Проверяем источники раз в час</small>
        </span>
      </section>
      <LibraryExplorer books={books.map(summarize)} />
      <section className="lib-how">
        <div>
          <span className="lib-kicker">С ЧЕГО НАЧАТЬ</span>
          <h2>
            Выбрать. Открыть.
            <br />
            Устроиться поудобнее.
          </h2>
          <Link href="/catalog/guide" className="lib-text-link">
            Короткая инструкция <ArrowUpRight size={16} />
          </Link>
        </div>
        <ol>
          <li>
            <span>01</span>
            <div>
              <h3>Найди свою манхву</h3>
              <p>По названию, альтернативному переводу или любимому жанру.</p>
            </div>
          </li>
          <li>
            <span>02</span>
            <div>
              <h3>Открой оглавление</h3>
              <p>
                Начни с первой главы или перейди к той, на которой остановился.
              </p>
            </div>
          </li>
          <li>
            <span>03</span>
            <div>
              <h3>Продолжай в Telegram</h3>
              <p>
                Главы находятся в каналах. Подпишись на интересные истории,
                чтобы следить за продолжением.
              </p>
            </div>
          </li>
        </ol>
      </section>
      <section className="lib-faq">
        <span className="lib-kicker">ПОПУЛЯРНЫЕ ВОПРОСЫ</span>
        <h2>Перед первой главой</h2>
        <details>
          <summary>Что такое манхва?</summary>
          <p>
            Так называют корейские комиксы. В этой подборке — истории разных
            жанров: фэнтези, экшен, романтика, комедия и драма.
          </p>
        </details>
        <details>
          <summary>Где находятся сами главы?</summary>
          <p>
            В Telegram-каналах из каталога. На странице каждой истории есть
            оглавление и ссылки на опубликованные PDF.
          </p>
        </details>
        <details>
          <summary>Почему количество глав отличается от других сайтов?</summary>
          <p>
            Здесь считаются подтверждённые публикации в наших каналах. Нумерация
            прологов и дополнительных глав, а также скорость выхода переводов
            могут различаться.
          </p>
        </details>
        <details>
          <summary>Нужна ли регистрация на сайте?</summary>
          <p>
            Каталог и оглавления открыты без регистрации. Для перехода к постам
            и подписки на каналы используй Telegram.
          </p>
        </details>
      </section>
    </>
  );
}
