import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Foldr — Academic Article Critic",
  description: "Upload academic articles and get AI-powered critique",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">{children}</body>
    </html>
  );
}
