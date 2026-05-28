export type ConsensusVerdict =
  | "Mostly aligned"
  | "Mixed evidence"
  | "Contradicts consensus";

export type BiasWarning =
  | "Overconfident language"
  | "Cherry-picked stats"
  | "Misleading graphs"
  | "Correlation vs causation"
  | "Small sample size"
  | "Funding conflict";

export interface CredibilityScore {
  score: number; // 1–10
  explanation: string;
  institutionKnown: boolean;
  conflictsOfInterest: boolean;
}

export interface ConsensusCheck {
  verdict: ConsensusVerdict;
  reasoning: string;
}

export interface MethodologyReview {
  score: number; // 1–10
  weaknesses: string[];
}

export interface BiasDetection {
  warnings: BiasWarning[];
  confidenceLevel: "Low" | "Medium" | "High";
  details: string;
}

export interface SupportingContext {
  summary: string;
  keyConcerns: string[];
  relatedStudies: {
    title: string;
    relation: "supports" | "contradicts";
    url?: string;
  }[];
}

export interface ArticleAnalysis {
  id: string;
  title: string;
  authors: string[];
  publishedYear: number;
  journal?: string;
  credibility: CredibilityScore;
  consensus: ConsensusCheck;
  methodology: MethodologyReview;
  bias: BiasDetection;
  overallTrustScore: number; // 1–10, computed or provided
  context: SupportingContext;
}

/** Weights used to compute the ranking score (must sum to 1) */
export interface RankingWeights {
  credibility: number;
  consensus: number;
  methodology: number;
  bias: number;
}

export const DEFAULT_WEIGHTS: RankingWeights = {
  credibility: 0.3,
  consensus: 0.25,
  methodology: 0.25,
  bias: 0.2,
};

/** Map consensus verdict to a numeric score */
export function consensusToScore(verdict: ConsensusVerdict): number {
  switch (verdict) {
    case "Mostly aligned":
      return 10;
    case "Mixed evidence":
      return 5;
    case "Contradicts consensus":
      return 1;
  }
}

/** Map bias confidence + warning count to a score (higher = less biased) */
export function biasToScore(bias: BiasDetection): number {
  const warningPenalty = bias.warnings.length * 1.5;
  const confidencePenalty =
    bias.confidenceLevel === "High" ? 3 : bias.confidenceLevel === "Medium" ? 1.5 : 0;
  return Math.max(1, 10 - warningPenalty - confidencePenalty);
}

/** Compute weighted ranking score for an article */
export function computeRankingScore(
  article: ArticleAnalysis,
  weights: RankingWeights
): number {
  const credScore = article.credibility.score;
  const consScore = consensusToScore(article.consensus.verdict);
  const methScore = article.methodology.score;
  const biasScore = biasToScore(article.bias);

  return (
    credScore * weights.credibility +
    consScore * weights.consensus +
    methScore * weights.methodology +
    biasScore * weights.bias
  );
}
