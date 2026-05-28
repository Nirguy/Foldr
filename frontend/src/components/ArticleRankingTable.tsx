"use client";

import { useState, useMemo } from "react";
import {
  ArticleAnalysis,
  RankingWeights,
  DEFAULT_WEIGHTS,
  computeRankingScore,
} from "@/types/article";
import ArticleCard from "./ArticleCard";

interface WeightSliderProps {
  label: string;
  value: number;
  onChange: (v: number) => void;
}

function WeightSlider({ label, value, onChange }: WeightSliderProps) {
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <div className="flex justify-between text-xs text-gray-400">
        <span>{label}</span>
        <span className="font-mono text-blue-400">{(value * 100).toFixed(0)}%</span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        step={5}
        value={Math.round(value * 100)}
        onChange={(e) => onChange(Number(e.target.value) / 100)}
        className="w-full accent-blue-500 cursor-pointer"
        aria-label={`${label} weight`}
      />
    </div>
  );
}

interface ArticleRankingTableProps {
  articles: ArticleAnalysis[];
}

export default function ArticleRankingTable({
  articles,
}: ArticleRankingTableProps) {
  const [weights, setWeights] = useState<RankingWeights>(DEFAULT_WEIGHTS);
  const [showWeights, setShowWeights] = useState(false);

  // Normalise weights so they always sum to 1
  function setWeight(key: keyof RankingWeights, raw: number) {
    setWeights((prev) => {
      const next = { ...prev, [key]: raw };
      const total = Object.values(next).reduce((a, b) => a + b, 0);
      if (total === 0) return prev;
      return {
        credibility: next.credibility / total,
        consensus: next.consensus / total,
        methodology: next.methodology / total,
        bias: next.bias / total,
      };
    });
  }

  const ranked = useMemo(() => {
    return [...articles]
      .map((a) => ({ article: a, score: computeRankingScore(a, weights) }))
      .sort((a, b) => b.score - a.score);
  }, [articles, weights]);

  const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);
  const weightsBalanced = Math.abs(totalWeight - 1) < 0.01;

  return (
    <div className="flex flex-col gap-4">
      {/* ── Weight customisation panel ── */}
      <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <button
          onClick={() => setShowWeights((v) => !v)}
          className="w-full flex items-center justify-between px-5 py-3 hover:bg-gray-800/40 transition-colors"
          aria-expanded={showWeights}
        >
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-gray-200">
              Ranking Weights
            </span>
            {!weightsBalanced && (
              <span className="text-xs text-amber-400 border border-amber-700 rounded-full px-2 py-0.5">
                Normalising…
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex gap-3 text-xs text-gray-500">
              <span>Credibility {(weights.credibility * 100).toFixed(0)}%</span>
              <span>Consensus {(weights.consensus * 100).toFixed(0)}%</span>
              <span>Methodology {(weights.methodology * 100).toFixed(0)}%</span>
              <span>Bias {(weights.bias * 100).toFixed(0)}%</span>
            </div>
            <span className="text-gray-500">{showWeights ? "▲" : "▼"}</span>
          </div>
        </button>

        {showWeights && (
          <div className="px-5 pb-5 pt-2 border-t border-gray-800 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <WeightSlider
              label="Credibility"
              value={weights.credibility}
              onChange={(v) => setWeight("credibility", v)}
            />
            <WeightSlider
              label="Consensus"
              value={weights.consensus}
              onChange={(v) => setWeight("consensus", v)}
            />
            <WeightSlider
              label="Methodology"
              value={weights.methodology}
              onChange={(v) => setWeight("methodology", v)}
            />
            <WeightSlider
              label="Bias Detection"
              value={weights.bias}
              onChange={(v) => setWeight("bias", v)}
            />
            <div className="sm:col-span-2 lg:col-span-4 flex justify-end">
              <button
                onClick={() => setWeights(DEFAULT_WEIGHTS)}
                className="text-xs text-gray-500 hover:text-gray-300 underline transition-colors"
              >
                Reset to defaults
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Ranked list ── */}
      {ranked.length === 0 ? (
        <p className="text-center text-gray-600 py-12">
          No articles to rank yet.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {ranked.map(({ article, score }, idx) => (
            <ArticleCard
              key={article.id}
              article={article}
              rank={idx + 1}
              rankingScore={score}
            />
          ))}
        </div>
      )}
    </div>
  );
}
