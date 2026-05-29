"use client";

import { useState, useMemo, useRef, useEffect } from "react";
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
        <span className="font-mono text-blue-400">
          {(value * 100).toFixed(0)}%
        </span>
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

  const prevRankRef = useRef<Record<string, number>>({});
  const [changedIds, setChangedIds] = useState<Set<string>>(new Set());

  function setWeight(key: keyof RankingWeights, raw: number) {
    setWeights((prev) => {
      const next = { ...prev, [key]: raw };
      const total = Object.values(next).reduce((a, b) => a + b, 0);
      if (total === 0) return prev;
      return {
        credibility: next.credibility / total,
        bias: next.bias / total,
        aiDetection: next.aiDetection / total,
      };
    });
  }

  const ranked = useMemo(() => {
    return [...articles]
      .map((a) => ({ article: a, score: computeRankingScore(a, weights) }))
      .sort((a, b) => b.score - a.score);
  }, [articles, weights]);

  useEffect(() => {
    const newRanks: Record<string, number> = {};
    const changed = new Set<string>();

    ranked.forEach(({ article }, idx) => {
      const newRank = idx + 1;
      newRanks[article.id] = newRank;
      if (
        prevRankRef.current[article.id] !== undefined &&
        prevRankRef.current[article.id] !== newRank
      ) {
        changed.add(article.id);
      }
    });

    if (changed.size > 0) {
      setChangedIds(changed);
      const t = setTimeout(() => setChangedIds(new Set()), 1200);
      return () => clearTimeout(t);
    }

    prevRankRef.current = newRanks;
  }, [ranked]);

  useEffect(() => {
    const newRanks: Record<string, number> = {};
    ranked.forEach(({ article }, idx) => {
      newRanks[article.id] = idx + 1;
    });
    prevRankRef.current = newRanks;
  }, [ranked]);

  return (
    <div className="flex flex-col gap-3">
      {/* Weight panel */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <button
          onClick={() => setShowWeights((v) => !v)}
          className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-gray-800/40 transition-colors"
          aria-expanded={showWeights}
        >
          <span className="text-sm font-semibold text-gray-200">
            Ranking Weights
          </span>
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex gap-3 text-xs text-gray-500">
              <span>Cred {(weights.credibility * 100).toFixed(0)}%</span>
              <span>Bias {(weights.bias * 100).toFixed(0)}%</span>
              <span>AI {(weights.aiDetection * 100).toFixed(0)}%</span>
            </div>
            <span className="text-gray-500 text-xs">
              {showWeights ? "▲" : "▼"}
            </span>
          </div>
        </button>

        {showWeights && (
          <div className="px-4 pb-4 pt-2 border-t border-gray-800 grid grid-cols-1 sm:grid-cols-3 gap-4">
            <WeightSlider
              label="Credibility"
              value={weights.credibility}
              onChange={(v) => setWeight("credibility", v)}
            />
            <WeightSlider
              label="Bias Detection"
              value={weights.bias}
              onChange={(v) => setWeight("bias", v)}
            />
            <WeightSlider
              label="AI Detection"
              value={weights.aiDetection}
              onChange={(v) => setWeight("aiDetection", v)}
            />
            <div className="sm:col-span-3 flex justify-end">
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

      {/* Column header */}
      <div className="hidden sm:flex items-center gap-3 px-4 text-[9px] uppercase tracking-widest text-gray-600 select-none">
        <span className="w-6 text-center">#</span>
        <span className="flex-1">Article</span>
        <div className="flex gap-4 border-l border-gray-800 pl-4 pr-2">
          <span className="w-8 text-center">Cred</span>
          <span className="w-8 text-center">Bias</span>
          <span className="w-8 text-center">AI</span>
        </div>
        <div className="flex gap-3 border-l border-gray-800 pl-4">
          <span className="w-10 text-center">Score</span>
        </div>
        <span className="w-4" />
      </div>

      {/* Ranked list */}
      {ranked.length === 0 ? (
        <p className="text-center text-gray-600 py-12">
          No articles to rank yet.
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {ranked.map(({ article, score }, idx) => (
            <ArticleCard
              key={article.id}
              article={article}
              rank={idx + 1}
              rankingScore={score}
              rankChanged={changedIds.has(article.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
