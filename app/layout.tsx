import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SEI — Inteligência Económica",
  description: "Contexto macroeconómico, fontes verificáveis e ferramentas para decidir com clareza.",
  other: {
    "codex-preview": "development",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-PT">
      <body className="antialiased">{children}</body>
    </html>
  );
}
