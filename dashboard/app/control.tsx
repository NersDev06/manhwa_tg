"use client";
import { useCallback, useEffect, useState } from "react";
import {
  Sun,
  Pause,
  Play,
  Database,
  Moon,
  Activity,
  ArrowDown,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Layers3,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  Radio,
  RefreshCw,
  Search,
  ShieldCheck,
  TriangleAlert,
  Users,
  WifiOff,
} from "lucide-react";
type Channel = {
  id: string;
  title: string;
  enabled: boolean;
  checked: string;
  error: string | null;
  source: string;
  fallback_missing?: string[];
  available_sources?: string[];
  source_health?: Record<
    string,
    {
      state: string;
      chapters?: number;
      updated: string;
      http_status?: number;
      error?: string;
      images_enabled?: boolean;
    }
  >;
  stats: {
    subscribers: number;
    linked_chat_id?: number;
    username?: string;
    updated: string;
  } | null;
  counts: Record<string, number>;
  latest?: string;
};
type Issue = {
  id: string;
  subscription: string;
  name: string;
  number: string;
  status: string;
  error?: string;
  attempts: number;
  preview: boolean;
  phase?: string;
};
type Job = {
  _id: string;
  subscription: string;
  name: string;
  number: string;
  status: string;
  error?: string;
  attempts: number;
  sent_at?: string;
  retry_at?: string;
};
type State = {
  at: string;
  online: boolean;
  paused: boolean;
  events: {
    _id: string;
    at: string;
    kind: string;
    subscription?: string;
    number?: string;
    source?: string;
    error_type?: string;
  }[];
  worker: {
    stage: string;
    host?: string;
    chapter_delay?: number;
    title?: string;
    chapter?: string;
    page?: number;
    pages?: number;
    part?: number;
    parts?: number;
    upload_sent?: number;
    upload_total?: number;
    peak_memory_mb?: number;
    database_bytes?: number;
    updated?: string;
    heartbeat?: string;
    error?: string;
  } | null;
  channels: Channel[];
  recent: {
    id: string;
    subscription: string;
    name: string;
    number: string;
    sent_at: string;
    bytes?: number;
  }[];
  issues: Issue[];
  hours: { _id: string; count: number }[];
};
const number = (n: number) => new Intl.NumberFormat("ru").format(n);
const time = (s?: string) =>
  s
    ? new Date(s).toLocaleTimeString("ru", {
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Bishkek",
      })
    : "—";
const statuses: Record<string, string> = {
  pending: "В очереди",
  sent: "Опубликовано",
  failed: "Ошибка",
  uncertain: "Нужна проверка",
  processing: "Подготовка",
  sending: "Отправка",
};
export default function Control({ initialAuth }: { initialAuth: boolean }) {
  const [theme, setTheme] = useState("dark");
  useEffect(() => {
    const saved = localStorage.getItem("frame-theme");
    if (saved === "light" || saved === "dark") setTheme(saved);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  function toggleTheme() {
    const value = theme === "dark" ? "light" : "dark";
    setTheme(value);
    localStorage.setItem("frame-theme", value);
  }
  const [authed, setAuthed] = useState(initialAuth),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [data, setData] = useState<State | null>(null),
    [tab, setTab] = useState("overview"),
    [filter, setFilter] = useState(""),
    [channel, setChannel] = useState(""),
    [status, setStatus] = useState("pending"),
    [offset, setOffset] = useState(0),
    [jobs, setJobs] = useState<Job[]>([]),
    [total, setTotal] = useState(0),
    [queueError, setQueueError] = useState("");
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  async function pause(paused: boolean, subscription?: string) {
    setActionBusy(true);
    setActionError("");
    try {
      const r = await fetch("/api/control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paused, subscription }),
      });
      const value = await r.json();
      if (!r.ok) throw Error(value.error);
      await refresh();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Ошибка управления");
    } finally {
      setActionBusy(false);
    }
  }
  const refresh = useCallback(async () => {
    try {
      const r = await fetch("/api/state", { cache: "no-store" });
      if (r.status === 401) {
        setAuthed(false);
        return;
      }
      const value = await r.json();
      if (!r.ok) throw Error(value.error);
      setData(value);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Нет связи с сервером");
    }
  }, []);
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [tab]);
  useEffect(() => {
    if (!authed) return;
    void refresh();
    const timer = setInterval(() => void refresh(), 15000);
    return () => clearInterval(timer);
  }, [authed, refresh]);
  useEffect(() => {
    if (!authed || tab !== "queue") return;
    const controller = new AbortController();
    void fetch(
      "/api/jobs?" +
        new URLSearchParams({ channel, status, offset: String(offset) }),
      { signal: controller.signal },
    )
      .then(async (r) => {
        const v = await r.json();
        if (!r.ok) throw Error(v.error);
        setJobs(v.jobs);
        setTotal(v.total);
        setQueueError("");
      })
      .catch((e) => {
        if (e.name !== "AbortError") setQueueError(e.message);
      });
    return () => controller.abort();
  }, [authed, tab, channel, status, offset, data?.at]);
  async function login(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await fetch("/api/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const v = await r.json();
      if (!r.ok) throw Error(v.error);
      setPassword("");
      setAuthed(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка входа");
    } finally {
      setBusy(false);
    }
  }
  const count = (key: string) =>
    data?.channels.reduce((n, c) => n + (c.counts[key] || 0), 0) || 0;
  const sent = count("sent"),
    pending = count("pending"),
    attention = count("failed") + count("uncertain");
  const title = (id: string) =>
    data?.channels.find((c) => c.id === id)?.title || id;
  const goQueue = (id = "", state = "pending") => {
    setChannel(id);
    setStatus(state);
    setOffset(0);
    setTab("queue");
  };
  if (!authed)
    return (
      <main className="login">
        <div className="login-art" aria-hidden="true">
          <div className="book b1" />
          <div className="book b2" />
          <div className="book b3" />
          <span>
            FRAME
            <br />
            CONTROL
          </span>
        </div>
        <form onSubmit={login} className="login-form">
          <div className="brand">
            <Layers3 size={25} /> FRAME <small>MANHWA NETWORK</small>
          </div>
          <p className="eyebrow">ЛИЧНЫЙ КАБИНЕТ</p>
          <h1>
            Всё под
            <br />
            контролем.
          </h1>
          <p className="muted">
            Публикации, очередь и состояние твоих каналов — в одном месте.
          </p>
          <label htmlFor="password">Пароль доступа</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button className="primary" disabled={busy}>
            {busy ? "Подключение…" : "Открыть панель"}{" "}
            <ArrowUpRight size={18} />
          </button>
          <small className="muted">
            <ShieldCheck size={14} /> Закрытый доступ · данные не индексируются
          </small>
        </form>
      </main>
    );
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Layers3 size={28} />
          <span>
            FRAME<small>MANHWA CONTROL</small>
          </span>
        </div>
        <div className="workspace">
          <span className="workspace-icon">M</span>
          <span>
            Моя сеть
            <small>{data?.channels.length || "—"} каналов Telegram</small>
          </span>
          <Radio size={16} />
        </div>
        <p className="nav-label">РАБОЧЕЕ ПРОСТРАНСТВО</p>
        <nav>
          {[
            ["overview", "Обзор", LayoutDashboard],
            ["queue", "Очередь глав", Layers3],
            ["channels", "Каналы", BookOpen],
            ["issues", "События", Activity],
            ["sources", "Источники", Database],
          ].map(([id, label, Icon]) => {
            const I = Icon as typeof Activity;
            return (
              <button
                key={String(id)}
                className={tab === id ? "active" : ""}
                onClick={() => setTab(String(id))}
              >
                <I size={18} />
                {String(label)}
                {id === "issues" && attention > 0 && <b>{attention}</b>}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-box">
            <span className={"led " + (data?.online ? "on" : "")} />
            <strong>
              {data?.worker?.host === "heroku"
                ? "Облачный воркер"
                : "Локальный воркер"}
            </strong>
            <p>
              {data?.worker?.host === "heroku"
                ? "Публикации выполняются на Heroku. Ноутбук можно выключить."
                : "Публикации выполняются на твоём компьютере."}
            </p>
            <small>
              {data?.worker?.host === "heroku"
                ? `Basic · пауза ${data.worker.chapter_delay || 10} сек.`
                : "Heroku отключён"}
            </small>
          </div>
          <button
            className="logout"
            onClick={async () => {
              await fetch("/api/session", { method: "DELETE" });
              setAuthed(false);
              setData(null);
            }}
          >
            <LogOut size={16} /> Выйти
          </button>
        </div>
      </aside>
      <div className="content">
        <header>
          <div className="breadcrumb">
            Моя сеть <span>/</span>{" "}
            {
              (
                {
                  overview: "Обзор",
                  queue: "Очередь глав",
                  channels: "Каналы",
                  issues: "События",
                  sources: "Источники",
                } as Record<string, string>
              )[tab]
            }
          </div>
          <div className="header-right">
            <span className="live">
              <i /> Обновление каждые 15 сек.
            </span>
            <button
              className="theme-toggle"
              onClick={toggleTheme}
              aria-label={
                theme === "dark"
                  ? "Включить светлую тему"
                  : "Включить тёмную тему"
              }
            >
              {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <span className="avatar">N</span>
          </div>
        </header>
        <main className="main">
          <div className="page-heading">
            <div>
              <p className="eyebrow">ОПЕРАЦИОННЫЙ ЦЕНТР / TELEGRAM</p>
              <h1>
                {tab === "overview"
                  ? "Панель управления"
                  : tab === "queue"
                    ? "Очередь публикаций"
                    : tab === "channels"
                      ? "Твоя сеть каналов"
                      : tab === "sources"
                        ? "Резервные источники"
                        : "Журнал работы"}
                <span className="title-dot">.</span>
              </h1>
              <p className="muted">
                {tab === "overview"
                  ? "Все главы на своих местах. Каждый процесс — на виду."
                  : tab === "queue"
                    ? "Порядок глав, повторные попытки и результаты отправки."
                    : tab === "channels"
                      ? "Живые показатели и состояние публикаций каждого тайтла."
                      : tab === "sources"
                        ? "Доступность каталогов и автоматическая смена источника."
                        : "История публикаций, настройки и главы, требующие проверки."}
              </p>
            </div>
            <button className="secondary" onClick={() => void refresh()}>
              <RefreshCw size={16} /> Обновить
            </button>
          </div>
          {error && (
            <div role="alert" className="notice error">
              <WifiOff size={18} />
              {error}
              {data && " · Показаны последние полученные данные"}
            </div>
          )}
          {!data && !error && (
            <div className="loading">
              <RefreshCw className="spin" /> Подключаемся к сети каналов…
            </div>
          )}
          {data && (
            <>
              {tab === "overview" && (
                <>
                  <section className="hero">
                    <div className="hero-copy">
                      <span
                        className={
                          "status-pill " + (data.online ? "green" : "amber")
                        }
                      >
                        <span className={"led " + (data.online ? "on" : "")} />
                        {data.online ? "Воркер на связи" : "Воркер не на связи"}
                      </span>
                      <h2>
                        Истории продолжаются.
                        <br />
                        <span>Публикации — под контролем.</span>
                      </h2>
                      <p>
                        {data.paused &&
                        data.worker?.stage !== "uploading" &&
                        data.worker?.stage !== "preparing"
                          ? "Автопубликация приостановлена. Главы ждут в очереди."
                          : data.worker?.stage === "uploading"
                            ? `Отправляется PDF · ${data.worker.title}, глава ${data.worker.chapter}`
                            : data.worker?.stage === "preparing"
                              ? `Готовим главу ${data.worker.chapter} · ${data.worker.title}`
                              : attention
                                ? `${attention} ${attention === 1 ? "глава требует" : "глав требуют"} проверки. Остальные каналы продолжают свою очередь.`
                                : "Наблюдаем за источниками и отправляем главы по очереди."}
                      </p>
                      <button onClick={() => goQueue()} className="hero-link">
                        Посмотреть очередь <ArrowUpRight size={17} />
                      </button>
                    </div>
                    <div className="hero-scene" aria-hidden="true">
                      <div className="scene-grid" />
                      <div className="stack">
                        <div className="sheet s4" />
                        <div className="sheet s3" />
                        <div className="sheet s2" />
                        <div className="sheet s1">
                          <div className="sheet-top">
                            FRAME <ArrowUpRight size={25} />
                          </div>
                          <div className="sheet-mark">
                            M<span>+</span>
                          </div>
                          <div className="sheet-bottom">
                            MANHWA NETWORK<span>08 / LIVE</span>
                          </div>
                        </div>
                      </div>
                      <div className="scene-caption">
                        <span className="led on" /> SEQUENTIAL PUBLISHING
                      </div>
                    </div>
                  </section>
                  <section className="metrics">
                    {[
                      {
                        label: "В очереди",
                        value: pending,
                        foot: "глав ожидают публикации",
                        icon: Layers3,
                        state: "pending",
                      },
                      {
                        label: "Опубликовано",
                        value: sent,
                        foot: "глав с подтверждением Telegram",
                        icon: Check,
                        state: "sent",
                      },
                      {
                        label: "Подписчики",
                        value: data.channels.reduce(
                          (n, c) => n + (c.stats?.subscribers || 0),
                          0,
                        ),
                        foot: `сумма по ${data.channels.filter((c) => c.stats).length} каналам, без дедупликации`,
                        icon: Users,
                        state: null,
                      },
                      {
                        label: "Требуют внимания",
                        value: attention,
                        foot: "ошибки и неопределённая доставка",
                        icon: TriangleAlert,
                        state: "uncertain",
                      },
                    ].map((m) => (
                      <button
                        className="metric"
                        key={m.label}
                        onClick={() =>
                          m.state ? goQueue("", m.state) : setTab("channels")
                        }
                      >
                        <span>
                          {m.label}
                          <m.icon size={18} />
                        </span>
                        <strong>{number(m.value)}</strong>
                        <small>{m.foot}</small>
                      </button>
                    ))}
                  </section>
                  <section className="middle-grid">
                    <div className="panel current">
                      <div className="panel-heading">
                        <h2>
                          <Radio size={17} /> Сейчас в работе
                        </h2>
                        <span className="micro">LIVE PROCESS</span>
                      </div>
                      <div className="current-title">
                        <span className="chapter-icon">
                          <BookOpen />
                        </span>
                        <div>
                          <h3>
                            {data.worker?.stage === "preparing" ||
                            data.worker?.stage === "uploading"
                              ? data.worker.title
                              : data.paused
                                ? "Публикации на паузе"
                                : "Ожидание следующей главы"}
                          </h3>
                          <p className="muted">
                            {data.worker?.stage === "preparing" ||
                            data.worker?.stage === "uploading"
                              ? `Глава ${data.worker.chapter}`
                              : data.online
                                ? data.paused
                                  ? "Нажми «Продолжить всё» для возобновления"
                                  : "Воркер проверяет очередь и источники"
                                : "Воркер не на связи — проверь состояние сервера"}
                          </p>
                        </div>
                      </div>
                      <div className="pipeline">
                        {["Источник", "Подготовка PDF", "Telegram"].map(
                          (step, i) => (
                            <div
                              key={step}
                              className={
                                data.online &&
                                ((data.worker?.stage === "uploading" &&
                                  i === 2) ||
                                  (data.worker?.stage === "preparing" &&
                                    i === 1))
                                  ? "running"
                                  : ""
                              }
                            >
                              <span>{String(i + 1).padStart(2, "0")}</span>
                              <strong>{step}</strong>
                            </div>
                          ),
                        )}
                      </div>
                      <div className="progress">
                        <i
                          style={{
                            width:
                              data.worker?.stage === "preparing" &&
                              data.worker.pages
                                ? `${((data.worker.page || 0) / data.worker.pages) * 100}%`
                                : data.worker?.stage === "uploading"
                                  ? `${Math.min(100, ((data.worker.upload_sent || 0) / Math.max(1, data.worker.upload_total || 1)) * 100)}%`
                                  : "0%",
                          }}
                        />
                      </div>
                      <div className="progress-caption">
                        <span>
                          {data.worker?.stage === "preparing"
                            ? `${data.worker.page || 0} / ${data.worker.pages || "—"} изображений`
                            : data.worker?.stage === "uploading"
                              ? `Передано ${((data.worker.upload_sent || 0) / 1000000).toFixed(1)} / ${((data.worker.upload_total || 0) / 1000000).toFixed(1)} МБ · PDF ${data.worker.part}/${data.worker.parts}`
                              : "Последний сигнал воркера"}
                        </span>
                        <span>{time(data.worker?.heartbeat)} · Бишкек</span>
                      </div>
                    </div>
                    <div className="panel activity">
                      <div className="panel-heading">
                        <h2>Публикации за 24 часа</h2>
                        <span className="micro">
                          {number(data.hours.reduce((n, h) => n + h.count, 0))}{" "}
                          ГЛАВ
                        </span>
                      </div>
                      <div
                        className="bar-chart"
                        role="img"
                        aria-label="Количество опубликованных глав по часам за последние сутки"
                      >
                        {Array.from({ length: 24 }, (_, i) => {
                          const hour = new Date(
                            Date.now() - (23 - i) * 3600000,
                          );
                          hour.setUTCMinutes(0, 0, 0);
                          const value =
                            data.hours.find(
                              (h) =>
                                new Date(h._id).getTime() === hour.getTime(),
                            )?.count || 0;
                          const max = Math.max(
                            1,
                            ...data.hours.map((h) => h.count),
                          );
                          return (
                            <div
                              key={i}
                              title={`${time(hour.toISOString())}: ${value} глав`}
                            >
                              <i
                                style={{
                                  height: `${Math.max(2, (value / max) * 100)}%`,
                                }}
                              />
                            </div>
                          );
                        })}
                      </div>
                      <div className="chart-labels">
                        <span>24 часа назад</span>
                        <span>Сейчас</span>
                      </div>
                    </div>
                  </section>
                </>
              )}
              {(tab === "overview" || tab === "channels") && (
                <section className="panel publisher-controls">
                  <div>
                    <strong>
                      {data.paused
                        ? "Публикации на паузе"
                        : "Автопубликация включена"}
                    </strong>
                    <p>
                      Пауза действует после текущей главы. Очередь и готовые PDF
                      сохраняются.
                    </p>
                    {actionError && <p role="alert">{actionError}</p>}
                  </div>
                  <button
                    className="text-button"
                    disabled={actionBusy}
                    onClick={() => void pause(!data.paused)}
                  >
                    {data.paused ? <Play size={16} /> : <Pause size={16} />}{" "}
                    {data.paused ? "Продолжить всё" : "Приостановить всё"}
                  </button>
                </section>
              )}
              {(tab === "overview" || tab === "channels") && (
                <section className="panel channel-panel">
                  <div className="panel-heading">
                    <h2>
                      Каналы{" "}
                      <span className="count-badge">
                        {data.channels.length}
                      </span>
                    </h2>
                    <label className="search">
                      <Search size={16} />
                      <input
                        aria-label="Поиск каналов"
                        placeholder="Найти канал…"
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                      />
                    </label>
                  </div>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>ТАЙТЛ / КАНАЛ</th>
                          <th>ПУБЛИКАЦИИ</th>
                          <th>ПОДПИСЧИКИ</th>
                          <th>КОММЕНТАРИИ</th>
                          <th>СОСТОЯНИЕ</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {data.channels
                          .filter((c) =>
                            c.title
                              .toLowerCase()
                              .includes(filter.toLowerCase()),
                          )
                          .map((c, i) => {
                            const problem =
                              (c.counts.failed || 0) +
                              (c.counts.uncertain || 0);
                            const total = Object.values(c.counts).reduce(
                              (a, b) => a + b,
                              0,
                            );
                            return (
                              <tr key={c.id}>
                                <td>
                                  <div className="channel-name">
                                    <span className={"tile tile-" + i}>
                                      {c.title.charAt(0)}
                                    </span>
                                    <div>
                                      <strong>{c.title}</strong>
                                      <small>
                                        {c.stats?.username
                                          ? "@" + c.stats.username
                                          : c.source}
                                      </small>
                                    </div>
                                  </div>
                                </td>
                                <td>
                                  <strong>
                                    {c.counts.sent || 0}{" "}
                                    <span className="muted">/ {total}</span>
                                  </strong>
                                  <div className="mini-progress">
                                    <i
                                      style={{
                                        width: `${((c.counts.sent || 0) / Math.max(1, total)) * 100}%`,
                                      }}
                                    />
                                  </div>
                                </td>
                                <td>
                                  {c.stats ? number(c.stats.subscribers) : "—"}
                                  <small className="muted">
                                    {c.stats
                                      ? time(c.stats.updated)
                                      : "нет данных"}
                                  </small>
                                </td>
                                <td>
                                  <span
                                    className={
                                      "discussion " +
                                      (c.stats?.linked_chat_id ? "enabled" : "")
                                    }
                                  >
                                    <MessageCircle size={14} />
                                    {c.stats?.linked_chat_id
                                      ? "Подключены"
                                      : "Не подключены"}
                                  </span>
                                  <small className="muted">
                                    {c.stats?.linked_chat_id
                                      ? "Число не доступно в Bot API"
                                      : "Нужна группа обсуждения"}
                                  </small>
                                </td>
                                <td>
                                  <span
                                    className={
                                      "state-badge " +
                                      (problem
                                        ? "amber"
                                        : c.enabled
                                          ? "green"
                                          : "neutral")
                                    }
                                  >
                                    {problem
                                      ? `${problem} на проверке`
                                      : c.enabled
                                        ? "В очереди"
                                        : "На паузе"}
                                  </span>
                                  <small className="muted">
                                    {c.source}
                                    {!!c.fallback_missing?.length &&
                                      ` · нет ${c.fallback_missing.length} доп. глав`}
                                    {c.error ? " · ошибка проверки" : ""}
                                  </small>
                                </td>
                                <td>
                                  <button
                                    className="icon-button"
                                    disabled={actionBusy}
                                    aria-label={
                                      (c.enabled ? "Пауза: " : "Продолжить: ") +
                                      c.title
                                    }
                                    onClick={() => void pause(c.enabled, c.id)}
                                  >
                                    {c.enabled ? (
                                      <Pause size={16} />
                                    ) : (
                                      <Play size={16} />
                                    )}
                                  </button>
                                  <button
                                    className="icon-button"
                                    aria-label={"Очередь: " + c.title}
                                    onClick={() => goQueue(c.id)}
                                  >
                                    <ArrowUpRight size={18} />
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}
              {tab === "queue" && (
                <section className="panel">
                  <div className="queue-filters">
                    <select
                      aria-label="Канал"
                      value={channel}
                      onChange={(e) => {
                        setChannel(e.target.value);
                        setOffset(0);
                      }}
                    >
                      <option value="">Все каналы</option>
                      {data.channels.map((c) => (
                        <option value={c.id} key={c.id}>
                          {c.title}
                        </option>
                      ))}
                    </select>
                    <select
                      aria-label="Статус"
                      value={status}
                      onChange={(e) => {
                        setStatus(e.target.value);
                        setOffset(0);
                      }}
                    >
                      {Object.entries(statuses).map(([key, label]) => (
                        <option key={key} value={key}>
                          {label}
                        </option>
                      ))}
                    </select>
                    <span className="muted">{number(total)} глав</span>
                  </div>
                  {queueError && (
                    <p role="alert" className="error">
                      {queueError}
                    </p>
                  )}
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>ГЛАВА</th>
                          <th>КАНАЛ</th>
                          <th>СТАТУС</th>
                          <th>ПОПЫТКИ</th>
                          <th>ДЕТАЛИ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {jobs.map((j) => (
                          <tr key={j._id}>
                            <td>
                              <strong>{j.name}</strong>
                            </td>
                            <td>{title(j.subscription)}</td>
                            <td>
                              <span className="state-badge">
                                {statuses[j.status]}
                              </span>
                            </td>
                            <td>{j.attempts}</td>
                            <td className="job-detail">
                              {j.error ||
                                (j.sent_at
                                  ? `Отправлено в ${time(j.sent_at)}`
                                  : j.retry_at
                                    ? `Повтор после ${time(j.retry_at)}`
                                    : "Ожидает своей очереди")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {jobs.length === 0 && !queueError && (
                      <p className="empty">
                        Здесь пока нет глав с этим статусом.
                      </p>
                    )}
                  </div>
                  <div className="pagination">
                    <span>
                      {total ? offset + 1 : 0}–{Math.min(offset + 30, total)} из{" "}
                      {number(total)}
                    </span>
                    <div>
                      <button
                        aria-label="Предыдущая страница"
                        disabled={offset === 0}
                        onClick={() => setOffset(Math.max(0, offset - 30))}
                      >
                        <ChevronLeft size={18} />
                      </button>
                      <button
                        aria-label="Следующая страница"
                        disabled={offset + 30 >= total}
                        onClick={() => setOffset(offset + 30)}
                      >
                        <ChevronRight size={18} />
                      </button>
                    </div>
                  </div>
                </section>
              )}
              {tab === "sources" && (
                <section className="sources-grid">
                  <div className="panel source-intro">
                    <ShieldCheck size={24} />
                    <div>
                      <h2>Одна глава — одна публикация</h2>
                      <p>
                        При сбое берём целую главу из следующего источника.
                        Номер главы и история отправок сохраняются. ReManga
                        отдаёт только открытые бесплатные главы.
                      </p>
                    </div>
                  </div>
                  {data.channels.map((c) => (
                    <article className="panel source-card" key={c.id}>
                      <div className="panel-heading">
                        <h2>{c.title}</h2>
                        <span className="count-badge">
                          {c.available_sources?.length || 0} доступны
                        </span>
                      </div>
                      <p className="muted">Последний источник: {c.source}</p>
                      {Object.entries(c.source_health || {}).map(
                        ([key, health]) => (
                          <div className="source-line" key={key}>
                            <span
                              className={
                                "source-dot " +
                                (health.state === "available" ? "ok" : "bad")
                              }
                            />
                            <div>
                              <strong>
                                {{
                                  mangashi: "MangaShi",
                                  wamanga: "WaManga",
                                  mangabuff: "MangaBuff",
                                  remanga: "ReManga",
                                }[key] || key}
                              </strong>
                              <small>
                                {health.state === "available"
                                  ? `${health.chapters ?? "—"} глав${health.images_enabled === false ? " · только каталог, изображения отключены" : " в каталоге"}`
                                  : health.http_status
                                    ? `HTTP ${health.http_status} · используем резерв`
                                    : "Источник временно недоступен"}
                              </small>
                            </div>
                            <time>{time(health.updated)}</time>
                          </div>
                        ),
                      )}
                      {!!c.fallback_missing?.length && (
                        <p className="source-warning">
                          Нет в доступных резервах:{" "}
                          {c.fallback_missing.join(", ")}. Главы остаются в
                          очереди.
                        </p>
                      )}
                    </article>
                  ))}
                </section>
              )}
              {tab === "issues" && (
                <section className="issues-list">
                  {data.issues
                    .filter(
                      (j) => j.status === "uncertain" || j.status === "failed",
                    )
                    .map((j) => (
                      <article className="panel issue" key={j.id}>
                        <TriangleAlert size={22} />
                        <div>
                          <span className="state-badge amber">
                            {statuses[j.status]}
                          </span>
                          <h2>
                            {title(j.subscription)} · {j.name}
                          </h2>
                          <p>{j.error || "Нет описания ошибки"}</p>
                          <small className="muted">
                            Попыток: {j.attempts} ·{" "}
                            {j.preview
                              ? "Превью уже опубликовано"
                              : "Превью не подтверждено"}{" "}
                            · ID {j.id}
                          </small>
                          {j.status === "uncertain" && (
                            <p className="issue-help">
                              Сначала проверь наличие PDF в канале. Повтор без
                              проверки может создать дубликат.
                            </p>
                          )}
                        </div>
                      </article>
                    ))}
                  {attention === 0 && (
                    <div className="panel empty">
                      <ShieldCheck size={32} />
                      <h2>Всё спокойно</h2>
                      <p>Нет глав с ошибкой или неподтверждённой доставкой.</p>
                    </div>
                  )}
                </section>
              )}
              {tab === "issues" && (
                <section className="panel event-history">
                  <div className="panel-heading">
                    <h2>Журнал работы</h2>
                    <span className="count-badge">30 дней</span>
                  </div>
                  {!data.events?.length && (
                    <p className="muted">
                      Здесь появятся публикации, перезапуски и изменения
                      настроек.
                    </p>
                  )}
                  {data.events?.map((e) => (
                    <div className="recent-row" key={e._id}>
                      <span className="sent-icon">
                        <Activity size={15} />
                      </span>
                      <div>
                        <strong>
                          {{
                            published: "Глава опубликована",
                            worker_started: "Воркер запущен",
                            worker_stopped: "Воркер остановлен",
                            paused: "Публикации приостановлены",
                            resumed: "Публикации возобновлены",
                            job_failed: "Ошибка обработки",
                            delivery_uncertain: "Нужна проверка доставки",
                          }[e.kind] || e.kind}
                        </strong>
                        <small>
                          {e.subscription
                            ? title(e.subscription)
                            : "Все каналы"}
                          {e.number ? ` · Глава ${e.number}` : ""}
                          {e.source ? ` · ${e.source}` : ""}
                          {e.error_type ? ` · ${e.error_type}` : ""}
                        </small>
                      </div>
                      <time>
                        {new Date(e.at).toLocaleDateString("ru", {
                          timeZone: "Asia/Bishkek",
                          day: "2-digit",
                          month: "2-digit",
                        })}{" "}
                        · {time(e.at)}
                      </time>
                    </div>
                  ))}
                </section>
              )}
              {tab === "overview" && (
                <section className="panel recent">
                  <div className="panel-heading">
                    <h2>Последние публикации</h2>
                    <button
                      className="text-button"
                      onClick={() => goQueue("", "sent")}
                    >
                      Все главы <ArrowUpRight size={16} />
                    </button>
                  </div>
                  {data.recent.slice(0, 5).map((j) => (
                    <div className="recent-row" key={j.id}>
                      <span className="sent-icon">
                        <Check size={15} />
                      </span>
                      <div>
                        <strong>{title(j.subscription)}</strong>
                        <small>
                          {j.name} · PDF{" "}
                          {j.bytes
                            ? `${(j.bytes / 1000000).toFixed(1)} МБ`
                            : ""}
                        </small>
                      </div>
                      <time>{time(j.sent_at)}</time>
                    </div>
                  ))}
                </section>
              )}
              <footer>
                <span>
                  <ShieldCheck size={13} /> Данные из MongoDB · Telegram Bot API
                  {data.worker?.peak_memory_mb
                    ? ` · Воркер: ${data.worker.peak_memory_mb} МБ`
                    : ""}
                  {data.worker?.database_bytes
                    ? ` · База: ${(data.worker.database_bytes / 1048576).toFixed(1)} МБ`
                    : ""}
                </span>
                <span>Снимок: {time(data.at)} Бишкек · FRAME / 01</span>
              </footer>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
