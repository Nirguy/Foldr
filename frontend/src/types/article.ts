// ─── Credibility ────────────────────────────────────────────────────────────

export interface CredibilityScores {
  /** Overall credibility score 0–10 */
  score: number;
  /** Normalized citation count (MNCS) */
  citationScore: number | null;
  /** Number of retractions by the author */
  authorRetractions: number;
  /** Number of retractions by the journal */
  journalRetractions: number;
  /** Red flag: this specific article was retracted */
  articleRetracted: boolean;
  /** Red flag: journal is on predatory list */
  journalPredatory: boolean;
  /** Human-readable explanation of how the score was derived */
  explanation: string;
}

// ─── Bias ───────────────────────────────────────────────────────────────────

export interface BiasScores {
  /** Overall bias score 0–10 (higher = less biased) */
  score: number;
  /** Lie factor score 0–10 */
  lieFactor: number | null;
  /** Cherry picking score 0–10 */
  cherryPickingScore: number | null;
  /** Graph bias score 0–10 (placeholder for later) */
  graphBias: number | null;
  /** Human-readable explanation */
  explanation: string;
}

// ─── AI Detection ───────────────────────────────────────────────────────────

export interface SuspiciousImage {
  /** base64 PNG data */
  imageData: string;
  /** AI confidence score 0–1 */
  aiScore: number;
  /** Page number in the PDF */
  pageNumber: number;
  /** Reasons flagged */
  reasons: string[];
}

export interface AIDetectionScores {
  /** Overall AI detection score 0–10 (higher = more natural/trustworthy) */
  score: number;
  /** AI-generated image score 0–10 */
  imageScore: number;
  /** AI-generated dataset score 0–10 */
  datasetScore: number;
  /** Suspicious images to display */
  suspiciousImages: SuspiciousImage[];
  /** Human-readable explanation */
  explanation: string;
}

// ─── Article ────────────────────────────────────────────────────────────────

export interface ExtractedAsset {
  imageData: string;
  pageNumber: number;
  type: "chart" | "image";
  width: number;
  height: number;
}

export interface ArticleAnalysis {
  id: string;
  title: string;
  authors: string[];
  publishedYear: number;
  journal?: string;
  credibility: CredibilityScores;
  bias: BiasScores;
  aiDetection: AIDetectionScores;
  /** Overall trust score 0–10 */
  overallTrustScore: number;
  /** Extracted visual assets for debugging */
  extractedAssets: ExtractedAsset[];
}

// ─── Ranking ────────────────────────────────────────────────────────────────

export interface RankingWeights {
  credibility: number;
  bias: number;
  aiDetection: number;
}

export const DEFAULT_WEIGHTS: RankingWeights = {
  credibility: 0.4,
  bias: 0.3,
  aiDetection: 0.3,
};

/** Compute weighted ranking score for an article */
export function computeRankingScore(
  article: ArticleAnalysis,
  weights: RankingWeights
): number {
  return (
    article.credibility.score * weights.credibility +
    article.bias.score * weights.bias +
    article.aiDetection.score * weights.aiDetection
  );
}
