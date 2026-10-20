"use client";
import { useEffect, useMemo, useState } from "react";
import { Search, ArrowUpRight, Bookmark, Check } from "lucide-react";
import { chaptersLabel } from "@/lib/wording";
import type { Chapter } from "@/lib/library-types";
export default function ChapterDirectory({
  slug,
  chapters,
}: {
  slug: string;
  chapters: Chapter[];
}) {
  const [query, setQuery] = useState(""),
    [resume, setResume] = useState<{ number: string; url: string } | null>(
      null,
    );
  useEffect(() => {
    try {
      const x = JSON.parse(localStorage.getItem("frame-reading-v1") || "{}")[
        slug
      ];
      if (
        x &&
        chapters.some((c) => c.number === x.number && c.urls.includes(x.url))
      )
        setResume(x);
    } catch {}
    const hash = window.location.hash.slice(1);
    if (hash.startsWith("chapters-")) {
      const el = document.getElementById(hash);
      if (el instanceof HTMLDetailsElement) el.open = true;
    }
  }, [slug, chapters]);
  const groups = useMemo(
    () =>
      Array.from({ length: Math.ceil(chapters.length / 50) }, (_, i) => ({
        index: i,
        all: chapters.slice(i * 50, (i + 1) * 50),
        visible: chapters
          .slice(i * 50, (i + 1) * 50)
          .filter(
            (c) => !query || c.number.includes(query.trim().replace(",", ".")),
          ),
      })).filter((g) => g.visible.length),
    [chapters, query],
  );
  function remember(c: Chapter, url: string) {
    const value = { number: c.number, url };
    setResume(value);
    try {
      const saved = JSON.parse(
        localStorage.getItem("frame-reading-v1") || "{}",
      );
      saved[slug] = value;
      localStorage.setItem("frame-reading-v1", JSON.stringify(saved));
    } catch {}
  }
  return (
    <section id="chapters" className="lib-directory">
      <div className="lib-section-heading">
        <div>
          <span className="lib-kicker">ОТ ПЕРВОЙ ДО ПОСЛЕДНЕЙ</span>
          <h2>
            Оглавление <span>{chapters.length}</span>
          </h2>
        </div>
        <label className="lib-search">
          <Search size={19} />
          <input
            type="search"
            inputMode="decimal"
            aria-label="Найти главу по номеру"
            placeholder="Номер главы, например 104.1"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </div>
      {resume && (
        <a
          className="lib-resume"
          href={resume.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Bookmark size={18} />
          <span>
            Ты открывал главу {resume.number}
            <small>Продолжить чтение в Telegram</small>
          </span>
          <ArrowUpRight size={18} />
        </a>
      )}
      <p className="lib-directory-note">
        Нажми на главу, чтобы открыть её пост в Telegram. Отметка последней
        открытой главы сохраняется только в этом браузере.
      </p>
      {groups.map((g) => (
        <details
          key={g.index}
          id={"chapters-" + (g.index + 1)}
          className="lib-chapter-group"
          open={query ? true : undefined}
        >
          <summary>
            <span>
              Главы {g.all[0].number} — {g.all.at(-1)!.number}
            </span>
            <small>{chaptersLabel(g.visible.length)}</small>
          </summary>
          <div className="lib-chapter-grid">
            {g.visible.map((c) => (
              <div
                className={
                  "lib-chapter " +
                  (resume?.number === c.number ? "was-opened" : "")
                }
                key={c.volume + ":" + c.number}
              >
                <a
                  href={c.urls[0]}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => remember(c, c.urls[0])}
                >
                  <span>Глава {c.number}</span>
                  {resume?.number === c.number ? (
                    <Check size={14} />
                  ) : (
                    <ArrowUpRight size={13} />
                  )}
                </a>
                {c.urls.length > 1 && (
                  <div className="lib-parts">
                    {c.urls.map((url, i) => (
                      <a
                        key={url}
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={() => remember(c, url)}
                        aria-label={`Глава ${c.number}, часть ${i + 1}`}
                      >
                        {i + 1}/{c.urls.length}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </details>
      ))}
      {!groups.length && (
        <div className="lib-empty">
          <h3>Такой главы пока нет</h3>
          <p>
            Проверь номер или открой канал, чтобы посмотреть последние
            публикации.
          </p>
          <button onClick={() => setQuery("")}>Показать все главы</button>
        </div>
      )}
    </section>
  );
}
