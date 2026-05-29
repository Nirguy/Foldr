"use client";

import { useState } from "react";
import { ArticleAnalysis } from "@/types/article";

// ─── helpers ────────────────────────────────────────────────────────────────

function scoreColor(score: number, max = 10) {
  const pct = (score / max) * 100;
  if (pct >= 70) return "text-emerald-400";
  if (pct >= 40) return "text-amber-400";
  return "text-red-400";
}

function barFill(score: number, max = 10) {
  const pct = (score / max) * 100;
  if (pct >= 70) return "bg-emerald-500";
  if (pct >= 40) return "bg-amber-400";
  return "bg-red-500";
}

function ScoreBar({ score, max = 10 }: { score: number; max?: number }) {
  const pct = Math.min(100, (score / max) * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-gray-700 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barFill(score, max)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-xs font-mono w-8 text-right ${scoreColor(score, max)}`}>
        {score.toFixed(1)}
      </span>
    </div>
  );
}

function ScorePill({ label, score, max = 10 }: { label: string; score: number; max?: number }) {
  const pct = Math.min(100, (score / max) * 100);
  const fill = pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-400" : "bg-red-500";
  return (
    <div className="flex flex-col items-center gap-0.5 w-12">
      <span className="text-[9px] uppercase tracking-wider text-gray-500 leading-none">
        {label}
      </span>
      <span className={`text-sm font-bold leading-none ${scoreColor(score, max)}`}>
        {score.toFixed(1)}
      </span>
      <div className="w-full h-1 rounded-full bg-gray-700 overflow-hidden mt-0.5">
        <div
          className={`h-full rounded-full transition-all duration-500 ${fill}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function RedFlag({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-red-900/60 text-red-300 border border-red-700">
      🚩 {label}
    </span>
  );
}

function SubScore({ label, value }: { label: string; value: number | null }) {
  if (value === null) return (
    <div className="flex justify-between items-center text-xs">
      <span className="text-gray-400">{label}</span>
      <span className="text-gray-600">N/A</span>
    </div>
  );
  return (
    <div className="flex justify-between items-center text-xs">
      <span className="text-gray-400">{label}</span>
      <span className={scoreColor(value)}>{value.toFixed(1)}/10</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-gray-800 rounded-xl p-3 flex flex-col gap-2">
      <h3 className="text-[10px] font-semibold uppercase tracking-widest text-gray-500">
        {title}
      </h3>
      {children}
    </div>
  );
}

// ─── main component ──────────────────────────────────────────────────────────

interface ArticleCardProps {
  article: ArticleAnalysis;
  rank?: number;
  rankingScore?: number;
  defaultExpanded?: boolean;
  rankChanged?: boolean;
}

export default function ArticleCard({
  article,
  rank,
  rankingScore,
  defaultExpanded = false,
  rankChanged = false,
}: ArticleCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div
      className={`bg-gray-900 border rounded-xl overflow-hidden transition-all duration-300 ${
        rankChanged
          ? "border-blue-500 shadow-[0_0_12px_2px_rgba(59,130,246,0.25)]"
          : "border-gray-800"
      }`}
    >
      {/* ── Collapsed header ── */}
      <div className="flex items-center gap-3 px-4 py-2.5">
        {rank !== undefined && (
          <span className="text-base font-black text-gray-600 w-6 shrink-0 text-center">
            {rank}
          </span>
        )}

        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex-1 min-w-0 text-left"
          aria-expanded={expanded}
        >
          <p className="text-sm font-semibold text-gray-100 truncate leading-snug">
            {article.title}
          </p>
          <p className="text-[11px] text-gray-500 truncate">
            {article.authors.join(", ")} · {article.publishedYear}
            {article.journal ? ` · ${article.journal}` : ""}
          </p>
        </button>

        {/* Score pills */}
        <div className="hidden sm:flex items-center gap-4 shrink-0 border-l border-gray-800 pl-4">
          <ScorePill label="Cred" score={article.credibility.score} />
          <ScorePill label="Bias" score={article.bias.score} />
          <ScorePill label="AI" score={article.aiDetection.score} />
        </div>

        {/* Rank + Trust */}
        <div className="flex items-center gap-3 shrink-0 border-l border-gray-800 pl-4">
          {rankingScore !== undefined && (
            <div className="text-right">
              <p className="text-[9px] text-gray-500 uppercase tracking-wide">Score</p>
              <p className="text-sm font-bold text-blue-400">{rankingScore.toFixed(2)}</p>
            </div>
          )}
        </div>

        {/* Red flags inline */}
        {(article.credibility.articleRetracted || article.credibility.journalPredatory) && (
          <div className="hidden lg:flex items-center gap-1 shrink-0 pl-2">
            {article.credibility.articleRetracted && <RedFlag label="Retracted" />}
            {article.credibility.journalPredatory && <RedFlag label="Predatory" />}
          </div>
        )}

        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-gray-600 hover:text-gray-300 transition-colors text-xs ml-1 shrink-0"
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          {expanded ? "▲" : "▼"}
        </button>
      </div>

      {/* ── Expanded detail ── */}
      {expanded && (
        <div className="border-t border-gray-800 px-4 pb-4 pt-3 flex flex-col gap-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">

            {/* Credibility */}
            <Section title="Credibility">
              <ScoreBar score={article.credibility.score} />
              <div className="space-y-1 mt-1">
                <SubScore label="Citation impact (MNCS)" value={article.credibility.citationScore} />
                <SubScore label="Author retractions" value={article.credibility.authorRetractions === 0 ? 10 : Math.max(0, 10 - article.credibility.authorRetractions * 3)} />
                <SubScore label="Journal retractions" value={article.credibility.journalRetractions === 0 ? 10 : Math.max(0, 10 - article.credibility.journalRetractions * 2)} />
              </div>
              {/* Red flags */}
              <div className="flex flex-wrap gap-1.5 mt-1">
                {article.credibility.articleRetracted && <RedFlag label="Article retracted" />}
                {article.credibility.journalPredatory && <RedFlag label="Predatory journal" />}
              </div>
              {!article.credibility.articleRetracted && !article.credibility.journalPredatory && (
                <p className="text-xs text-emerald-400">No red flags</p>
              )}
              {/* Explanation */}
              <div className="mt-2 p-2 rounded bg-gray-800/50 border border-gray-700">
                <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">How this was calculated:</p>
                <pre className="text-[11px] text-gray-400 whitespace-pre-wrap font-mono leading-relaxed">{article.credibility.explanation}</pre>
              </div>
            </Section>

            {/* Bias */}
            <Section title="Bias Detection">
              <ScoreBar score={article.bias.score} />
              <div className="space-y-1 mt-1">
                <SubScore label="Lie factor" value={article.bias.lieFactor} />
                <SubScore label="Cherry picking" value={article.bias.cherryPickingScore} />
                <SubScore label="Graph bias" value={article.bias.graphBias} />
              </div>
              {article.bias.graphBias === null && (
                <p className="text-[10px] text-gray-600 italic">Graph bias analysis coming soon</p>
              )}
              {/* Explanation */}
              <div className="mt-2 p-2 rounded bg-gray-800/50 border border-gray-700">
                <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">How this was calculated:</p>
                <pre className="text-[11px] text-gray-400 whitespace-pre-wrap font-mono leading-relaxed">{article.bias.explanation}</pre>
              </div>
            </Section>

            {/* AI Detection */}
            <Section title="AI Detection">
              <ScoreBar score={article.aiDetection.score} />
              <div className="space-y-1 mt-1">
                <SubScore label="Image authenticity" value={article.aiDetection.imageScore} />
                <SubScore label="Dataset authenticity" value={article.aiDetection.datasetScore} />
              </div>

              {/* Suspicious images */}
              {article.aiDetection.suspiciousImages.length > 0 && (
                <div className="mt-2">
                  <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">
                    Suspicious images ({article.aiDetection.suspiciousImages.length})
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    {article.aiDetection.suspiciousImages.slice(0, 4).map((img, i) => (
                      <div key={i} className="relative rounded-lg overflow-hidden border border-red-800/50">
                        <img
                          src={`data:image/png;base64,${img.imageData}`}
                          alt={`Suspicious image p.${img.pageNumber}`}
                          className="w-full h-20 object-cover"
                        />
                        <div className="absolute bottom-0 left-0 right-0 bg-black/70 px-1.5 py-0.5">
                          <p className="text-[9px] text-red-300">
                            p.{img.pageNumber} · {(img.aiScore * 100).toFixed(0)}% AI
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                  {article.aiDetection.suspiciousImages.length > 4 && (
                    <p className="text-[10px] text-gray-500 mt-1">
                      +{article.aiDetection.suspiciousImages.length - 4} more
                    </p>
                  )}
                </div>
              )}

              {/* Explanation */}
              <div className="mt-2 p-2 rounded bg-gray-800/50 border border-gray-700">
                <p className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">How this was calculated:</p>
                <pre className="text-[11px] text-gray-400 whitespace-pre-wrap font-mono leading-relaxed">{article.aiDetection.explanation}</pre>
              </div>
            </Section>
          </div>

          {/* Extracted Assets (temporary debug) */}
          {article.extractedAssets && article.extractedAssets.length > 0 && (
            <div className="border border-gray-800 rounded-xl p-3">
              <h3 className="text-[10px] font-semibold uppercase tracking-widest text-gray-500 mb-2">
                Extracted Assets ({article.extractedAssets.length})
              </h3>
              {/* Charts */}
              {article.extractedAssets.filter(a => a.type === "chart").length > 0 && (
                <div className="mb-3">
                  <p className="text-[10px] text-blue-400 mb-1">
                    Charts ({article.extractedAssets.filter(a => a.type === "chart").length})
                  </p>
                  <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                    {article.extractedAssets.filter(a => a.type === "chart").slice(0, 8).map((asset, i) => (
                      <div key={`chart-${i}`} className="relative rounded-lg overflow-hidden border border-blue-800/50">
                        <img
                          src={`data:image/png;base64,${asset.imageData}`}
                          alt={`Chart p.${asset.pageNumber}`}
                          className="w-full h-16 object-contain bg-white"
                        />
                        <div className="absolute bottom-0 left-0 right-0 bg-black/70 px-1 py-0.5">
                          <p className="text-[8px] text-blue-300">p.{asset.pageNumber} · {asset.width}×{asset.height}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                  {article.extractedAssets.filter(a => a.type === "chart").length > 8 && (
                    <p className="text-[10px] text-gray-500 mt-1">+{article.extractedAssets.filter(a => a.type === "chart").length - 8} more</p>
                  )}
                </div>
              )}
              {/* Images */}
              {article.extractedAssets.filter(a => a.type === "image").length > 0 && (
                <div>
                  <p className="text-[10px] text-green-400 mb-1">
                    Images ({article.extractedAssets.filter(a => a.type === "image").length})
                  </p>
                  <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                    {article.extractedAssets.filter(a => a.type === "image").slice(0, 8).map((asset, i) => (
                      <div key={`img-${i}`} className="relative rounded-lg overflow-hidden border border-green-800/50">
                        <img
                          src={`data:image/png;base64,${asset.imageData}`}
                          alt={`Image p.${asset.pageNumber}`}
                          className="w-full h-16 object-contain bg-white"
                        />
                        <div className="absolute bottom-0 left-0 right-0 bg-black/70 px-1 py-0.5">
                          <p className="text-[8px] text-green-300">p.{asset.pageNumber} · {asset.width}×{asset.height}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                  {article.extractedAssets.filter(a => a.type === "image").length > 8 && (
                    <p className="text-[10px] text-gray-500 mt-1">+{article.extractedAssets.filter(a => a.type === "image").length - 8} more</p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
