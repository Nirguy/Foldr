"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArticleAnalysis,
  BiasWarning,
  ConsensusVerdict,
  biasToScore,
  consensusToScore,
} from "@/types/article";
import Tooltip from "./Tooltip";

// ─── helpers ────────────────────────────────────────────────────────────────

function scoreColor(score: number, max = 10) {
  const pct = (score / max) * 100;
  if (pct >= 70) return "text-emerald-400";
  if (pct >= 40) return "text-amber-400";
  return "text-red-400";
}

function ScoreBar({ score, max = 10 }: { score: number; max?: number }) {
  const pct = (score / max) * 100;
  const fill =
    pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-400" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-gray-700 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${fill}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-xs font-mono w-8 text-right ${scoreColor(score, max)}`}>
        {score.toFixed(1)}
      </span>
    </div>
  );
}

/** Compact numeric pill shown in the collapsed row */
function ScorePill({
  label,
  score,
  max = 10,
}: {
  label: string;
  score: number;
  max?: number;
}) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className="text-[9px] uppercase tracking-wider text-gray-500 leading-none">
        {label}
      </span>
      <span className={`text-sm font-bold leading-none ${scoreColor(score, max)}`}>
        {score.toFixed(1)}
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

function biasVariant(_w: BiasWarning): "warn" {
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
  /** flash highlight when rank just changed */
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

  const trustColor = scoreColor(article.overallTrustScore);

  // Derived sub-scores for the pills
  const consensusScore = consensusToScore(article.consensus.verdict);
  const biasScore = biasToScore(article.bias);

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
        {/* Rank */}
        {rank !== undefined && (
          <span className="text-base font-black text-gray-600 w-6 shrink-0 text-center">
            {rank}
          </span>
        )}

        {/* Title + meta — clickable to expand */}
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
          <ScorePill label="Cons" score={consensusScore} />
          <ScorePill label="Meth" score={article.methodology.score} />
          <ScorePill label="Bias" score={biasScore} />
        </div>

        {/* Rank score + Trust with tooltips */}
        <div className="flex items-center gap-3 shrink-0 border-l border-gray-800 pl-4">
          {rankingScore !== undefined && (
            <Tooltip content="Rank score: your weighted combination of Credibility, Consensus, Methodology, and Bias scores. Adjust the sliders above to change how each dimension is weighted.">
              <div className="text-right cursor-help">
                <p className="text-[9px] text-gray-500 uppercase tracking-wide flex items-center gap-0.5">
                  Rank <span className="text-gray-600">ⓘ</span>
                </p>
                <p className="text-sm font-bold text-blue-400">
                  {rankingScore.toFixed(2)}
                </p>
              </div>
            </Tooltip>
          )}
          <Tooltip content="Trust score: a fixed aggregate of all analysis dimensions (credibility, consensus, methodology, bias) at equal weight. Unlike Rank score, it does not change when you adjust the sliders.">
            <div className="text-right cursor-help">
              <p className="text-[9px] text-gray-500 uppercase tracking-wide flex items-center gap-0.5">
                Trust <span className="text-gray-600">ⓘ</span>
              </p>
              <p className={`text-sm font-bold ${trustColor}`}>
                {article.overallTrustScore.toFixed(1)}
              </p>
            </div>
          </Tooltip>
        </div>

        {/* Expand toggle */}
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
          {/* Open full article link */}
          <div className="flex justify-end">
            <Link
              href={`/article/${article.id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-400 hover:text-blue-300 hover:underline transition-colors flex items-center gap-1"
            >
              Open full article view ↗
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* A. Credibility */}
            <Section title="A · Credibility Score">
              <ScoreBar score={article.credibility.score} />
              <p className="text-xs text-gray-300 leading-relaxed">
                {article.credibility.explanation}
              </p>
              <div className="flex flex-wrap gap-1.5">
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
                  variant={article.credibility.conflictsOfInterest ? "bad" : "good"}
                />
              </div>
            </Section>

            {/* B. Consensus */}
            <Section title="B · Consensus Check">
              <Badge
                label={article.consensus.verdict}
                variant={verdictVariant(article.consensus.verdict)}
              />
              <p className="text-xs text-gray-300 leading-relaxed">
                {article.consensus.reasoning}
              </p>
            </Section>

            {/* C. Methodology */}
            <Section title="C · Methodology Review">
              <ScoreBar score={article.methodology.score} />
              {article.methodology.weaknesses.length > 0 ? (
                <ul className="space-y-1">
                  {article.methodology.weaknesses.map((w, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-1.5 text-xs text-gray-300"
                    >
                      <span className="text-amber-400 mt-0.5 shrink-0">⚠</span>
                      {w}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-emerald-400">
                  No major weaknesses identified.
                </p>
              )}
            </Section>

            {/* D. Bias */}
            <Section title="D · Bias & Manipulation">
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-gray-500">Confidence:</span>
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
                <div className="flex flex-wrap gap-1.5">
                  {article.bias.warnings.map((w, i) => (
                    <Badge key={i} label={w} variant={biasVariant(w)} />
                  ))}
                </div>
              ) : (
                <p className="text-xs text-emerald-400">No bias flags detected.</p>
              )}
              <p className="text-xs text-gray-300 leading-relaxed">
                {article.bias.details}
              </p>
            </Section>

            {/* E. Overall Trust */}
            <Section title="E · Overall Trust Score">
              <div className="flex items-center gap-3">
                <span className={`text-4xl font-black ${trustColor}`}>
                  {article.overallTrustScore.toFixed(1)}
                </span>
                <div className="flex-1">
                  <ScoreBar score={article.overallTrustScore} />
                  <p className="text-[10px] text-gray-500 mt-1">
                    Aggregated from credibility, consensus, methodology, and bias.
                  </p>
                </div>
              </div>
            </Section>

            {/* F. Supporting Context */}
            <Section title="F · Supporting Context">
              <p className="text-xs text-gray-300 leading-relaxed">
                {article.context.summary}
              </p>
              {article.context.keyConcerns.length > 0 && (
                <div>
                  <p className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide">
                    Key concerns
                  </p>
                  <ul className="space-y-0.5">
                    {article.context.keyConcerns.map((c, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-1.5 text-xs text-gray-300"
                      >
                        <span className="text-red-400 mt-0.5 shrink-0">•</span>
                        {c}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {article.context.relatedStudies.length > 0 && (
                <div>
                  <p className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide">
                    Related studies
                  </p>
                  <ul className="space-y-0.5">
                    {article.context.relatedStudies.map((s, i) => (
                      <li key={i} className="flex items-center gap-1.5 text-xs">
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
        </div>
      )}
    </div>
  );
}
