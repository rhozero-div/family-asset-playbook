import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FAPM Demo Deploy",
  description: "Family Asset Playbook simulated frontend for Cloudflare Pages and Hugging Face Spaces.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
