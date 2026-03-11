import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MADO - Multi-Agent Dev Orchestrator",
  description: "Local AI development team management platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
