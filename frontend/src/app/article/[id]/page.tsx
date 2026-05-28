"use client";

import { use } from "react";
import { notFound } from "next/navigation";
import Link from "next/link";
import { MOCK_ARTICLES } from "@/lib/mockArticles";
import ArticleCard from "@/components/ArticleCard";

export default function ArticleDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const article = MOCK_ARTICLES.find((a) => a.id === id);
  if (!article) notFound();

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Top bar */}
      <header className="sticky top-0 z-10 flex items-center gap-3 px-6 py-3 border-b border-gray-800 bg-gray-950/90 backdrop-blur">
        <Link
          href="/"
          className="text-sm text-gray-400 hover:text-white transition-colors flex items-center gap-1"
        >
          ← Back
        </Link>
        <span className="text-gray-700">|</span>
        <h1 className="text-sm font-semibold text-gray-200 truncate">
          {article.title}
        </h1>
      </header>

      <div className="max-w-6xl mx-auto p-6 flex flex-col lg:flex-row gap-6">
        {/* Left: full analysis card */}
        <div className="flex-1 min-w-0">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-3">
            Full Analysis
          </h2>
          <ArticleCard article={article} defaultExpanded />
        </div>

        {/* Right: article viewer placeholder */}
        <div className="lg:w-[480px] shrink-0 flex flex-col gap-3">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500">
            Article
          </h2>
          <div className="flex-1 rounded-2xl border border-gray-800 bg-gray-900 flex flex-col items-center justify-center gap-4 p-8 min-h-[600px]">
            <div className="text-5xl">📄</div>
            <p className="text-gray-400 text-sm text-center max-w-xs">
              PDF viewer will appear here once the article is uploaded or
              fetched from the source.
            </p>
            {article.context.relatedStudies.some((s) => s.url) && (
              <a
                href={
                  article.context.relatedStudies.find((s) => s.url)?.url ?? "#"
                }
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-400 hover:underline"
              >
                View source →
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
