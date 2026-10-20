import Link from "next/link";
export default function NotFound() {
  return (
    <section className="lib-guide">
      <span className="lib-kicker">СТРАНИЦА НЕ НАЙДЕНА</span>
      <h1>
        Этой истории
        <br />
        на полке пока нет.
      </h1>
      <p>
        Возможно, адрес изменился. В каталоге можно найти произведение по
        названию.
      </p>
      <Link href="/catalog" className="lib-button">
        Вернуться к каталогу
      </Link>
    </section>
  );
}
