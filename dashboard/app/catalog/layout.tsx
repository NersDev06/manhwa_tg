import type { Metadata } from "next";
import Link from "next/link";
import { Layers3, ArrowUpRight } from "lucide-react";
import { SITE } from "@/lib/library";
import "./library.css";
export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  robots: { index: true, follow: true },
  title: {
    default: "Манхва на русском — каталог каналов | FRAME",
    template: "%s | FRAME",
  },
  description:
    "Каталог манхвы на русском: описания, варианты названий и оглавления с прямыми ссылками на главы в Telegram.",
};
export default function LibraryLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="library">
      <a className="lib-skip" href="#library-main">
        К содержимому
      </a>
      <header className="lib-header">
        <Link
          href="/catalog"
          className="lib-brand"
          aria-label="FRAME — каталог манхвы"
        >
          <Layers3 size={29} />
          <span>
            FRAME<small>БИБЛИОТЕКА МАНХВЫ</small>
          </span>
        </Link>
        <nav aria-label="Навигация каталога">
          <Link href="/catalog">Каталог</Link>
          <Link href="/catalog/guide">
            Как читать <ArrowUpRight size={14} />
          </Link>
        </nav>
        <span className="lib-header-note">
          <i /> На русском · в Telegram
        </span>
      </header>
      <main id="library-main">{children}</main>
      <footer className="lib-footer">
        <Link href="/catalog" className="lib-brand">
          <Layers3 size={23} />
          <span>
            FRAME<small>ИСТОРИИ, К КОТОРЫМ ВОЗВРАЩАЮТСЯ</small>
          </span>
        </Link>
        <div>
          <Link href="/catalog">Все произведения</Link>
          <Link href="/catalog/guide">Помощь читателю</Link>
          <span>Каталог читательских Telegram-каналов.</span>
        </div>
      </footer>
    </div>
  );
}
