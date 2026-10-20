"use client";
import { useMemo, useState } from "react";
import Link from "next/link";
import { Search, ArrowUpRight, ArrowRight, X } from "lucide-react";
import { chaptersLabel } from "@/lib/wording";
import type { BookSummary } from "@/lib/library-types";
const normalize = (s: string) =>
  s
    .toLocaleLowerCase("ru")
    .replaceAll("ё", "е")
    .replace(/[^\p{L}\p{N}]+/gu, " ");
export default function LibraryExplorer({ books }: { books: BookSummary[] }) {
  const [query, setQuery] = useState(""),
    [genre, setGenre] = useState("Все"),
    [order, setOrder] = useState("editorial");
  const genres = [
    "Все",
    "Фэнтези",
    "Экшен",
    "Регрессия",
    "Романтика",
    "Драма",
    "Комедия",
  ];
  const found = useMemo(
    () =>
      books
        .filter(
          (b) =>
            (genre === "Все" || b.genres.includes(genre)) &&
            normalize([b.title, b.english, ...b.aliases].join(" ")).includes(
              normalize(query),
            ),
        )
        .sort((a, b) =>
          order === "alphabet"
            ? a.title.localeCompare(b.title, "ru")
            : order === "chapters"
              ? b.count - a.count
              : order === "latest"
                ? (b.latestAt || "").localeCompare(a.latestAt || "")
                : 0,
        ),
    [books, genre, order, query],
  );
  return (
    <section id="titles" className="lib-titles">
      <div className="lib-section-heading">
        <div>
          <span className="lib-kicker">ВЫБРАТЬ СЛЕДУЮЩУЮ ИСТОРИЮ</span>
          <h2>
            На полке <span>{books.length}</span>
          </h2>
        </div>
        <label className="lib-search">
          <Search size={19} />
          <input
            type="search"
            aria-label="Поиск манхвы по названию"
            placeholder="Название на русском или английском…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {query && (
            <button onClick={() => setQuery("")} aria-label="Очистить поиск">
              <X size={17} />
            </button>
          )}
        </label>
      </div>
      <div className="lib-filters">
        <div className="lib-genres" aria-label="Жанры">
          {genres.map((g) => (
            <button
              key={g}
              aria-pressed={genre === g}
              className={genre === g ? "selected" : ""}
              onClick={() => setGenre(g)}
            >
              {g}
            </button>
          ))}
        </div>
        <label className="lib-order">
          Порядок{" "}
          <select
            aria-label="Порядок произведений"
            value={order}
            onChange={(e) => setOrder(e.target.value)}
          >
            <option value="editorial">На нашей полке</option>
            <option value="latest">Недавно обновились</option>
            <option value="chapters">Больше глав</option>
            <option value="alphabet">По алфавиту</option>
          </select>
        </label>
      </div>
      <p className="lib-results" role="status">
        Найдено произведений: {found.length}
      </p>
      <div className="lib-book-grid">
        {found.map((b, i) => (
          <article
            className="lib-book-card"
            key={b.slug}
            style={{ "--book-tone": b.tone } as React.CSSProperties}
          >
            <Link
              href={"/catalog/" + b.slug}
              className="lib-cover-scene"
              aria-label={"Открыть " + b.title}
            >
              <span className="lib-cover-number">
                {String(books.findIndex((x) => x.slug === b.slug) + 1).padStart(
                  2,
                  "0",
                )}
              </span>
              <div className="lib-cover-book">
                <img
                  src={b.cover}
                  alt={"Обложка манхвы «" + b.title + "»"}
                  width={b.coverWidth}
                  height={b.coverHeight}
                  loading={i < 4 ? "eager" : "lazy"}
                />
              </div>
              <span className="lib-cover-open">
                <ArrowUpRight size={20} />
              </span>
            </Link>
            <div className="lib-card-copy">
              <span className="lib-card-genre">
                {b.genres.slice(0, 2).join(" / ")}
              </span>
              <h3>
                <Link href={"/catalog/" + b.slug}>{b.title}</Link>
              </h3>
              <p>{b.description}</p>
              <div className="lib-card-bottom">
                <span>
                  {chaptersLabel(b.count)}{" "}
                  {b.latest && <small>Последняя: {b.latest}</small>}
                </span>
                <Link
                  href={"/catalog/" + b.slug}
                  aria-label={"Оглавление: " + b.title}
                >
                  <ArrowRight size={22} />
                </Link>
              </div>
            </div>
          </article>
        ))}
      </div>
      {!found.length && (
        <div className="lib-empty">
          <Search size={30} />
          <h3>Пока ничего не нашли</h3>
          <p>Попробуй другое название или убери фильтр жанра.</p>
          <button
            onClick={() => {
              setQuery("");
              setGenre("Все");
            }}
          >
            Сбросить фильтры
          </button>
        </div>
      )}
    </section>
  );
}
