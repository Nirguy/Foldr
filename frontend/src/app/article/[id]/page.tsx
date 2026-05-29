"use client";

import { use } from "react";
import Link from "next/link";

export default function ArticleDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="sticky top-0 z-10 flex items-center gap-3 px-6 py-3 border-b border-gray-800 bg-gray-950/90 backdrop-blur">
        <Link
          href="/"
          className="text-sm text-gray-400 hover:text-white transition-colors flex items-center gap-1"
        >
          ← Back
        </Link>
        <span className="text-gray-700">|</span>
        <h1 className="text-sm font-semibold text-gray-200 truncate">
          Article {id}
        </h1>
      </header>

      <div className="max-w-4xl mx-auto p-6">
        <div className="rounded-2xl border border-gray-800 bg-gray-900 flex flex-col items-center justify-center gap-4 p-12">
          <div className="text-5xl">📄</div>
          <p className="text-gray-400 text-sm text-center max-w-xs">
            Detailed article view coming soon.
          </p>
        </div>
      </div>
    </div>
  );
}
