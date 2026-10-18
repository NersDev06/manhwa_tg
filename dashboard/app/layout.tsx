import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "FRAME — Manhwa Control",
  description: "Панель управления публикациями",
  robots: { index: false, follow: false },
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru" data-theme="dark" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
