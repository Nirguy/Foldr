"use client";

import { useState } from "react";
import {
  ArticleAnalysis,
  BiasWarning,
  ConsensusVerdict,
} from "@/types/article";

// ─── helpers ────────────────────────────────────────────────────────────────

function ScoreBar({ score, max = 10 }: { score: number; max?: number }) {
  const pct = (score / max) * 100;
  const color =
    pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-400" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full bg-gray-700 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-mono text-gray-300 w-8 text-right">
        {score.toFixed(1)}/{max}
      </span>
    </div>
  );
}

function Badge({
  label,
  variant = "neutral",
}: {
  label: string;
  variant?: "good" | "warn" | "bad" | "neutral";
}) {
  const colors = {
    good: "bg-emerald-900/60 text-emerald-300 border-emerald-700",
    warn: "bg-amber-900/60 text-amber-300 border-amber-700",
    bad: "bg-red-900/60 text-red-300 border-red-700",
    neutral: "bg-gray-800 text-gray-300 border-gray-700",
  };
  return (
    <span
      className={`inline-block text-xs px-2 py-0.5 rounded-full border ${colors[variant]}`}
    >
      {label}
    </span>
  );
}

function verdictVariant(v: ConsensusVerdict): "good" | "warn" | "bad" {
  if (v === "Mostly aligned") return "good";
  if (v === "Mixed evidence") return "warn";
  return "bad";
}

function biasVariant(_w: BiasWarning): "warn" | "bad" {
  return "warn";
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-gray-800 rounded-xl p-4 flex flex-col gap-3">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-gray-500">
        {title}
      </h3>
      {children}
    </div>
  );
}

// ─── main component ──────────────────────────────────────────────────────────

interface ArticleCardProps {
  article: ArticleAnalysis;
  /** rank position in the table (1-based) */
  rank?: number;
  /** computed weighted score */
  rankingScore?: number;
  /** whether to start expanded */
  defaultExpanded?: boolean;
}

export default function ArticleCard({
  article,
  rank,
  rankingScore,
  defaultExpanded = false,
}: ArticleCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const trustColor =
    article.overallTrustScore >= 7
      ? "text-emerald-400"
      : article.overallTrustScore >= 4
      ? "text-amber-400"
      : "text-red-400";

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden transition-all duration-200">
      {/* ── Header (always visible) ── */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left px-5 py-4 flex items-start gap-4 hover:bg-gray-800/40 transition-colors"
        aria-expanded={expanded}
      >
        {rank !== undefined && (
          <span className="mt-0.5 text-2xl font-black text-gray-600 w-8 shrink-0 text-center">
            #{rank}
          </span>
        )}

        <div className="flex-1 min-w-0">
          <p className="font-semibold text-gray-100 truncate">{article.title}</p>
          <p className="text-xs text-gray-500 mt-0.5">
            {article.authors.join(", ")} · {article.publishedYear}
            {article.journal ? ` · ${article.journal}` : ""}
          </p>
        </div>

        <div className="flex items-center gap-4 shrink-0">
          {rankingScore !== undefined && (
            <div className="text-right">
              <p className="text-[10px] text-gray-500 uppercase tracking-wide">
                Rank score
              </p>
              <p className="text-lg font-bold text-blue-400">
                {rankingScore.toFixed(2)}
              </p>
            </div>
          )}
          <div className="text-right">
            <p className="text-[10px] text-gray-500 uppercase tracking-wide">
              Trust
            </p>
            <p className={`text-lg font-bold ${trustColor}`}>
              {article.overallTrustScore.toFixed(1)}
            </p>
          </div>
          <span className="text-gray-500 text-lg">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>

      {/* ── Expanded detail ── */}
      {expanded && (
        <div className="px-5 pb-5 grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-gray-800 pt-4">
          {/* A. Credibility Score */}
          <Section title="A · Credibility Score">
            <ScoreBar score={article.credibility.score} />
            <p className="text-sm text-gray-300 leading-relaxed">
              {article.credibility.explanation}
            </p>
            <div className="flex flex-wrap gap-2">
              <Badge
                label={
                  article.credibility.institutionKnown
                    ? "Known institution"
                    : "Unknown institution"
                }
                variant={article.credibility.institutionKnown ? "good" : "warn"}
              />
              <Badge
                label={
                  article.credibility.conflictsOfInterest
                    ? "Conflict of interest"
                    : "No conflict declared"
                }
                variant={
                  article.credibility.conflictsOfInterest ? "bad" : "good"
                }
              />
            </div>
          </Section>

          {/* B. Consensus Check */}
          <Section title="B · Consensus Check">
            <Badge
              label={article.consensus.verdict}
              variant={verdictVariant(article.consensus.verdict)}
            />
            <p className="text-sm text-gray-300 leading-relaxed">
              {article.consensus.reasoning}
            </p>
          </Section>

          {/* C. Methodology Review */}
          <Section title="C · Methodology Review">
            <ScoreBar score={article.methodology.score} />
            {article.methodology.weaknesses.length > 0 ? (
              <ul className="space-y-1">
                {article.methodology.weaknesses.map((w, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                    <span className="text-amber-400 mt-0.5">⚠</span>
                    {w}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-emerald-400">No major weaknesses identified.</p>
            )}
          </Section>

          {/* D. Bias / Manipulation Detection */}
          <Section title="D · Bias & Manipulation Detection">
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">Confidence:</span>
              <Badge
                label={article.bias.confidenceLevel}
                variant={
                  article.bias.confidenceLevel === "High"
                    ? "bad"
                    : article.bias.confidenceLevel === "Medium"
                    ? "warn"
                    : "good"
                }
              />
            </div>
            {article.bias.warnings.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {article.bias.warnings.map((w, i) => (
                  <Badge key={i} label={w} variant={biasVariant(w)} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-emerald-400">No bias flags detected.</p>
            )}
            <p className="text-sm text-gray-300 leading-relaxed">
              {article.bias.details}
            </p>
          </Section>

          {/* E. Overall Trust Score — full width */}
          <Section title="E · Overall Trust Score">
            <div className="flex items-center gap-4">
              <span className={`text-5xl font-black ${trustColor}`}>
                {article.overallTrustScore.toFixed(1)}
              </span>
              <div className="flex-1">
                <ScoreBar score={article.overallTrustScore} />
                <p className="text-xs text-gray-500 mt-1">
                  Aggregated from credibility, consensus, methodology, and bias
                  scores.
                </p>
              </div>
            </div>
          </Section>

          {/* F. Supporting Context — full width */}
          <Section title="F · Supporting Context">
            <p className="text-sm text-gray-300 leading-relaxed">
              {article.context.summary}
            </p>
            {article.context.keyConcerns.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 mb-1 uppercase tracking-wide">
                  Key concerns
                </p>
                <ul className="space-y-1">
                  {article.context.keyConcerns.map((c, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                      <span className="text-red-400 mt-0.5">•</span>
                      {c}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {article.context.relatedStudies.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 mb-1 uppercase tracking-wide">
                  Related studies
                </p>
                <ul className="space-y-1">
                  {article.context.relatedStudies.map((s, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm">
                      <span
                        className={
                          s.relation === "supports"
                            ? "text-emerald-400"
                            : "text-red-400"
                        }
                      >
                        {s.relation === "supports" ? "↑" : "↓"}
                      </span>
                      {s.url ? (
                        <a
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-400 hover:underline"
                        >
                          {s.title}
                        </a>
                      ) : (
                        <span className="text-gray-300">{s.title}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Section>
        </div>
      )}
    </div>
  );
}
