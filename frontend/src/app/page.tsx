"use client";

import { useState, useRef, useCallback } from "react";
import ArticleRankingTable from "@/components/ArticleRankingTable";
import { ArticleAnalysis } from "@/types/article";

type PaperStatus = {
  paper_id: string;
  filename: string;
  status: "uploading" | "extracting" | "complete" | "error";
  currentStep?: string;
  error?: string;
};

type Tab = "upload" | "analysis";

const API_BASE = "http://localhost:8000/api";

/** Transform raw backend paper data into the ArticleAnalysis shape the table expects */
function toArticleAnalysis(data: any, filename: string): ArticleAnalysis {
  const metadata = data.metadata || {};
  const metaEval = data.metadata_evaluation || {};
  const imageEval = data.image_evaluation || [];

  // ─── Credibility ───
  const isPredatory = metaEval.predatory_check === true;
  const journalName = metaEval.predatory_journal || metadata.journal || "Unknown";
  const mncs = metaEval.mncs_score;
  const citationScore = mncs != null ? Math.min(10, Math.max(0, mncs * 4)) : null;
  const authorRetractions = 0;
  const journalRetractions = 0;

  // Detect retracted articles from title
  const titleStr = (metadata.title || "").toLowerCase();
  const articleRetracted = titleStr.includes("retracted") || titleStr.includes("retraction");

  let credScore = 5;
  const credExplanationParts: string[] = [];

  if (articleRetracted) {
    credScore = 1;
    credExplanationParts.push(`Article title contains "RETRACTED" → credibility score set to minimum`);
  } else if (isPredatory) {
    credScore = 2;
    credExplanationParts.push(`Journal "${journalName}" found on Beall's predatory list → score heavily penalized`);
  } else if (citationScore != null) {
    credScore = Math.round(citationScore * 0.7 + 3);
    credExplanationParts.push(`MNCS = ${mncs!.toFixed(2)} (1.0 = field average). Normalized to ${citationScore.toFixed(1)}/10`);
  } else {
    credExplanationParts.push("Could not retrieve MNCS from OpenAlex → default score 5");
  }

  // Additional penalty if both retracted and predatory
  if (articleRetracted && isPredatory) {
    credScore = 0;
    credExplanationParts.push(`Also published in predatory journal "${journalName}" → score 0`);
  }

  if (metaEval.errors && metaEval.errors.length > 0) {
    credExplanationParts.push(`Errors: ${metaEval.errors.join("; ")}`);
  }

  credScore = Math.min(10, Math.max(0, credScore));
  credExplanationParts.push(`Final credibility score: ${credScore}/10`);

  // ─── Bias ───
  const cherryEval = data.cherry_picking_evaluation || {};
  const graphEval = data.graph_evaluation || {};
  const lieEval = data.lie_factor_evaluation || {};

  // Cherry picking: score is 0-100 (higher = more cherry-picked), invert to 0-10 (higher = less biased)
  const cherryRawScore = cherryEval.score ?? null;
  const cherryPickingScore = cherryRawScore != null ? Math.max(0, 10 - (cherryRawScore / 10)) : null;

  // Graph misleading: score is 0-10 (higher = more misleading), invert to 0-10 (higher = less biased)
  const graphRawScore = graphEval.score ?? null;
  const graphBias = graphRawScore != null ? Math.max(0, 10 - graphRawScore) : null;

  // Lie factor: ideal is 1.0, further from 1.0 = worse
  // Convert to 0-10 scale where 10 = perfect (lie factor = 1.0)
  const worstLieFactor = lieEval.worst_lie_factor ?? null;
  let lieFactor: number | null = null;
  if (worstLieFactor != null) {
    const deviation = Math.abs(worstLieFactor - 1.0);
    // deviation of 0 = score 10, deviation of 5+ = score 0
    lieFactor = Math.max(0, 10 - deviation * 2);
  }

  // Compute overall bias score from available sub-scores
  const biasSubScores = [cherryPickingScore, graphBias, lieFactor].filter((s): s is number => s != null);
  const biasScore = biasSubScores.length > 0
    ? biasSubScores.reduce((a, b) => a + b, 0) / biasSubScores.length
    : 5;

  // Build bias explanation
  const biasExplanationParts: string[] = [];
  if (cherryRawScore != null) {
    biasExplanationParts.push(`Cherry picking: raw score ${cherryRawScore}/100 (severity: ${cherryEval.severity || "N/A"})`);
    biasExplanationParts.push(`  → Inverted to ${cherryPickingScore!.toFixed(1)}/10 (higher = less biased)`);
    if (cherryEval.cherry_findings?.length > 0) {
      cherryEval.cherry_findings.forEach((f: any) => {
        biasExplanationParts.push(`  • ${f.type}: ${f.detail} (impact: ${f.impact})`);
      });
    }
  } else {
    const cherryErrors = cherryEval.errors || [];
    biasExplanationParts.push(`Cherry picking: not available${cherryErrors.length > 0 ? " — " + cherryErrors.join("; ") : ""}`);
  }

  if (worstLieFactor != null) {
    biasExplanationParts.push(`Lie factor: ${worstLieFactor.toFixed(3)} (ideal = 1.0, passed: ${lieEval.all_passed ? "yes" : "no"})`);
    biasExplanationParts.push(`  → Score: ${lieFactor!.toFixed(1)}/10`);
    if (lieEval.results?.length > 0) {
      lieEval.results.forEach((r: any) => {
        if (r.lie_factor != null) {
          biasExplanationParts.push(`  • Page ${r.page_number}: LF=${r.lie_factor.toFixed(3)} (${r.chart_type || "unknown"}) ${r.passed ? "✓" : "✗"}`);
        } else if (r.error) {
          biasExplanationParts.push(`  • Page ${r.page_number}: ${r.error}`);
        }
      });
    }
  } else {
    const lieErrors = lieEval.errors || [];
    biasExplanationParts.push(`Lie factor: not available${lieErrors.length > 0 ? " — " + lieErrors.join("; ") : ""}`);
  }

  if (graphRawScore != null) {
    biasExplanationParts.push(`Graph misleading: raw score ${graphRawScore.toFixed(1)}/10 (verdict: ${graphEval.verdict || "N/A"})`);
    biasExplanationParts.push(`  → Inverted to ${graphBias!.toFixed(1)}/10 (higher = less biased)`);
    if (graphEval.per_chart?.length > 0) {
      graphEval.per_chart.forEach((c: any) => {
        const issues = c.issues?.join(", ") || "none";
        biasExplanationParts.push(`  • Page ${c.page_number}: ${c.verdict} (${c.score?.toFixed(1)}/10) — ${issues}`);
      });
    }
  } else {
    const graphErrors = graphEval.errors || [];
    biasExplanationParts.push(`Graph analysis: not available${graphErrors.length > 0 ? " — " + graphErrors.join("; ") : ""}`);
  }

  biasExplanationParts.push(`Final bias score: ${biasScore.toFixed(1)}/10`);
  const biasExplanation = biasExplanationParts.join("\n");

  // ─── AI Detection ───
  const aiImages = imageEval.filter((img: any) => img.ai_label === "ai_generated");
  const totalImages = imageEval.length;
  const chartCount = imageEval.filter((img: any) => img.type === "chart").length;
  const photoCount = imageEval.filter((img: any) => img.type === "image").length;
  const imageScore = totalImages > 0
    ? Math.max(0, 10 - (aiImages.length / totalImages) * 10)
    : 10;
  const datasetScore = 10;
  const aiScore = (imageScore + datasetScore) / 2;

  const aiExplanationParts: string[] = [];
  aiExplanationParts.push(`${totalImages} visual asset(s) analyzed (${photoCount} images, ${chartCount} charts)`);
  if (aiImages.length > 0) {
    const aiCharts = aiImages.filter((img: any) => img.type === "chart").length;
    const aiPhotos = aiImages.filter((img: any) => img.type === "image").length;
    aiExplanationParts.push(`${aiImages.length} flagged as AI-generated (${aiPhotos} images, ${aiCharts} charts)`);
    aiImages.forEach((img: any) => {
      aiExplanationParts.push(`  • Page ${img.page_number} [${img.type}]: score ${img.ai_score?.toFixed(2)} — ${(img.ai_reasons || []).join(", ") || "no specific reason"}`);
    });
  } else if (totalImages > 0) {
    aiExplanationParts.push("No images or charts flagged as AI-generated");
  } else {
    aiExplanationParts.push("No images found in PDF");
  }
  aiExplanationParts.push(`Image authenticity: ${imageScore.toFixed(1)}/10, Dataset authenticity: ${datasetScore}/10 (not yet analyzed)`);
  aiExplanationParts.push(`Final AI score: ${aiScore.toFixed(1)}/10`);

  const suspiciousImages = aiImages
    .filter((img: any) => (img.ai_score || 0) >= 0.8)
    .map((img: any) => ({
      imageData: (data.visual_assets || []).find(
        (va: any) => va.page_number === img.page_number
      )?.image_data || "",
      aiScore: img.ai_score || 0,
      pageNumber: img.page_number || 0,
      reasons: img.ai_reasons || [],
    })).filter((img: any) => img.imageData);

  const overallTrustScore = Math.round((credScore * 0.4 + biasScore * 0.3 + aiScore * 0.3) * 10) / 10;

  return {
    id: data.paper_id,
    title: metadata.title || filename,
    authors: metadata.authors || [],
    publishedYear: metadata.date ? parseInt(metadata.date.slice(0, 4)) || 2024 : 2024,
    journal: metadata.journal || undefined,
    credibility: {
      score: credScore,
      citationScore,
      authorRetractions,
      journalRetractions,
      articleRetracted,
      journalPredatory: isPredatory,
      explanation: credExplanationParts.join("\n"),
    },
    bias: {
      score: biasScore,
      lieFactor,
      cherryPickingScore,
      graphBias,
      explanation: biasExplanation,
    },
    aiDetection: {
      score: aiScore,
      imageScore,
      datasetScore,
      suspiciousImages,
      explanation: aiExplanationParts.join("\n"),
    },
    overallTrustScore,
    extractedAssets: (data.visual_assets || []).map((va: any) => ({
      imageData: va.image_data || "",
      pageNumber: va.page_number || 0,
      type: va.type || "image",
      width: va.width || 0,
      height: va.height || 0,
    })),
  };
}

export default function Home() {
  const [papers, setPapers] = useState<PaperStatus[]>([]);
  const [urlInput, setUrlInput] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("upload");
  const [analysisData, setAnalysisData] = useState<ArticleAnalysis[]>([]);
  const [datasetFiles, setDatasetFiles] = useState<Map<string, File>>(new Map());
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [pendingPdfs, setPendingPdfs] = useState<File[]>([]);

  // Upload a single PDF file to the backend (with optional dataset)
  const uploadFile = useCallback(async (file: File, dataset?: File) => {
    const tempId = Math.random().toString(36).slice(2, 10);
    const entry: PaperStatus = {
      paper_id: tempId,
      filename: file.name,
      status: "uploading",
    };
    setPapers((prev) => [...prev, entry]);

    try {
      const formData = new FormData();
      formData.append("file", file);
      if (dataset) {
        formData.append("dataset", dataset);
      }

      const res = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Upload failed" }));
        setPapers((prev) =>
          prev.map((p) =>
            p.paper_id === tempId
              ? { ...p, status: "error", error: err.error || "Upload failed" }
              : p
          )
        );
        return;
      }

      const { paper_id } = await res.json();
      setPapers((prev) =>
        prev.map((p) =>
          p.paper_id === tempId
            ? { ...p, paper_id, status: "extracting" }
            : p
        )
      );

      // Poll for completion
      pollPaper(paper_id, file.name);
    } catch (e: any) {
      setPapers((prev) =>
        prev.map((p) =>
          p.paper_id === tempId
            ? { ...p, status: "error", error: e.message || "Network error" }
            : p
        )
      );
    }
  }, []);

  // Poll a paper until extraction is complete
  const pollPaper = useCallback(async (paperId: string, filename: string) => {
    const maxAttempts = 120; // 2 minutes max
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((r) => setTimeout(r, 1500));
      try {
        const res = await fetch(`${API_BASE}/papers/${paperId}`);
        if (!res.ok) continue;
        const data = await res.json();

        if (data.status === "complete") {
          setPapers((prev) =>
            prev.map((p) =>
              p.paper_id === paperId ? { ...p, status: "complete", currentStep: undefined } : p
            )
          );
          // Add to analysis data
          setAnalysisData((prev) => [...prev, toArticleAnalysis(data, filename)]);
          return;
        }

        // Update current step while still extracting
        if (data.current_step) {
          setPapers((prev) =>
            prev.map((p) =>
              p.paper_id === paperId ? { ...p, currentStep: data.current_step } : p
            )
          );
        }
      } catch {
        // Keep polling
      }
    }
    // Timeout
    setPapers((prev) =>
      prev.map((p) =>
        p.paper_id === paperId
          ? { ...p, status: "error", error: "Extraction timed out" }
          : p
      )
    );
  }, []);

  // Handle file drop
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files).filter(
      (f) => f.type === "application/pdf"
    );
    setPendingPdfs((prev) => [...prev, ...files]);
  };

  // Handle file input change (multiple)
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const pdfs = files.filter((f) => f.type === "application/pdf");
    setPendingPdfs((prev) => [...prev, ...pdfs]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // Start analysis: upload all pending PDFs with their paired datasets
  const handleStartAnalysis = () => {
    pendingPdfs.forEach((pdf) => {
      const dataset = datasetFiles.get(pdf.name);
      uploadFile(pdf, dataset);
    });
    setPendingPdfs([]);
    setDatasetFiles(new Map());
  };

  // Remove a pending PDF
  const removePendingPdf = (index: number) => {
    setPendingPdfs((prev) => {
      const name = prev[index]?.name;
      if (name) {
        setDatasetFiles((ds) => {
          const next = new Map(ds);
          next.delete(name);
          return next;
        });
      }
      return prev.filter((_, i) => i !== index);
    });
  };

  // Handle URL submission - TODO: will be connected to a service later
  const handleUrlSubmit = () => {
    const urls = urlInput
      .split("\n")
      .map((u) => u.trim())
      .filter((u) => u.length > 0);

    if (urls.length === 0) return;

    // Placeholder: mark as not yet supported
    urls.forEach((url) => {
      const tempId = Math.random().toString(36).slice(2, 10);
      const entry: PaperStatus = {
        paper_id: tempId,
        filename: url,
        status: "error",
        error: "URL fetching coming soon",
      };
      setPapers((prev) => [...prev, entry]);
    });

    setUrlInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && e.ctrlKey) {
      e.preventDefault();
      handleUrlSubmit();
    }
  };

  const completedCount = papers.filter((p) => p.status === "complete").length;
  const processingCount = papers.filter(
    (p) => p.status === "uploading" || p.status === "extracting"
  ).length;

  return (
    <div className="flex h-screen overflow-hidden flex-col">
      {/* Top bar */}
      <header className="flex items-center gap-3 px-6 py-3 border-b border-gray-800 shrink-0">
        <h1 className="text-lg font-bold tracking-tight">Foldr</h1>

        {/* Tabs */}
        <div className="ml-4 flex gap-1 bg-gray-800 rounded-lg p-1">
          <button
            onClick={() => setActiveTab("upload")}
            className={`text-sm px-3 py-1 rounded-md transition-colors ${
              activeTab === "upload"
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            Upload
          </button>
          <button
            onClick={() => setActiveTab("analysis")}
            className={`text-sm px-3 py-1 rounded-md transition-colors ${
              activeTab === "analysis"
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            Analysis {completedCount > 0 && `(${completedCount})`}
          </button>
        </div>

        {processingCount > 0 && (
          <span className="ml-auto flex items-center gap-2 text-xs text-yellow-400">
            <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            Processing {processingCount} article{processingCount > 1 ? "s" : ""}...
          </span>
        )}
      </header>

      {/* ── Upload Tab ── */}
      {activeTab === "upload" && (
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-3xl mx-auto space-y-8">
            <div>
              <h2 className="text-xl font-bold text-gray-100">
                Upload Articles
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                Upload one or more PDFs, or paste article URLs to analyze.
              </p>
            </div>

            {/* PDF Upload Area */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`w-full border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
                isDragging
                  ? "border-blue-500 bg-blue-500/10"
                  : "border-gray-700 hover:border-gray-500"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                multiple
                onChange={handleFileSelect}
                className="hidden"
                aria-label="Upload PDF articles"
              />
              <div className="space-y-2">
                <p className="text-3xl">📄</p>
                <p className="text-gray-300 font-medium">
                  Drop PDF files here, or click to browse
                </p>
                <p className="text-gray-500 text-sm">
                  Supports multiple files. Max 200MB per file.
                </p>
              </div>
            </div>

            {/* Pending PDFs list with dataset pairing */}
            {pendingPdfs.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-gray-300">
                  Staged articles ({pendingPdfs.length})
                </h3>
                <div className="space-y-2">
                  {pendingPdfs.map((pdf, idx) => (
                    <div
                      key={`${pdf.name}-${idx}`}
                      className="rounded-lg bg-gray-900 px-4 py-3 text-sm space-y-2"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-blue-400">📄</span>
                        <span className="flex-1 truncate text-gray-300">{pdf.name}</span>
                        <button
                          onClick={(e) => { e.stopPropagation(); removePendingPdf(idx); }}
                          className="text-gray-500 hover:text-red-400 transition-colors"
                          aria-label={`Remove ${pdf.name}`}
                        >
                          ✕
                        </button>
                      </div>
                      <div className="flex items-center gap-2 pl-7">
                        {datasetFiles.has(pdf.name) ? (
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-green-400 flex items-center gap-1">
                              📊 {datasetFiles.get(pdf.name)!.name}
                            </span>
                            <button
                              onClick={() => {
                                setDatasetFiles((prev) => {
                                  const next = new Map(prev);
                                  next.delete(pdf.name);
                                  return next;
                                });
                              }}
                              className="text-xs text-gray-500 hover:text-red-400"
                            >
                              ✕
                            </button>
                          </div>
                        ) : (
                          <label className="text-xs text-gray-500 hover:text-blue-400 cursor-pointer transition-colors flex items-center gap-1">
                            <span>+ Attach dataset (CSV/Excel)</span>
                            <input
                              type="file"
                              accept=".csv,.tsv,.xlsx,.xls"
                              className="hidden"
                              onChange={(e) => {
                                const f = e.target.files?.[0];
                                if (f) {
                                  setDatasetFiles((prev) => {
                                    const next = new Map(prev);
                                    next.set(pdf.name, f);
                                    return next;
                                  });
                                }
                                e.target.value = "";
                              }}
                            />
                          </label>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Start Analysis button */}
                <div className="text-center pt-2">
                  <button
                    onClick={handleStartAnalysis}
                    className="px-6 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 font-medium transition-colors"
                  >
                    Start Analysis ({pendingPdfs.length} article{pendingPdfs.length > 1 ? "s" : ""})
                  </button>
                </div>
              </div>
            )}

            {/* URL Input */}
            <div className="space-y-3">
              <label className="block text-sm font-medium text-gray-300">
                Or paste article URLs (one per line)
              </label>
              <textarea
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={"https://arxiv.org/pdf/2301.00001.pdf\nhttps://example.com/paper.pdf"}
                rows={4}
                className="w-full resize-none rounded-lg bg-gray-900 border border-gray-700 px-4 py-3 text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                aria-label="Article URLs input"
              />
              <div className="flex items-center gap-3">
                <button
                  onClick={handleUrlSubmit}
                  disabled={!urlInput.trim()}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed font-medium text-sm transition-colors"
                >
                  Fetch & Analyze
                </button>
                <span className="text-xs text-gray-500">
                  Ctrl+Enter to submit
                </span>
              </div>
            </div>

            {/* Status List */}
            {papers.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wide">
                  Queue ({papers.length})
                </h3>
                <div className="space-y-1">
                  {papers.map((paper) => (
                    <div
                      key={paper.paper_id}
                      className="rounded-lg bg-gray-900 px-4 py-2 text-sm"
                    >
                      <div className="flex items-center gap-3">
                        <span className="shrink-0">
                          {paper.status === "uploading" && (
                            <svg className="w-4 h-4 animate-spin text-blue-400" viewBox="0 0 24 24" fill="none">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                            </svg>
                          )}
                          {paper.status === "extracting" && (
                            <svg className="w-4 h-4 animate-spin text-yellow-400" viewBox="0 0 24 24" fill="none">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                            </svg>
                          )}
                          {paper.status === "complete" && (
                            <svg className="w-4 h-4 text-emerald-400" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"/>
                            </svg>
                          )}
                          {paper.status === "error" && (
                            <svg className="w-4 h-4 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd"/>
                            </svg>
                          )}
                        </span>
                        <span className="flex-1 truncate text-gray-300">
                          {paper.filename}
                        </span>
                        <span className="text-xs text-gray-500">
                          {paper.status === "uploading" && "Uploading..."}
                          {paper.status === "complete" && "Done"}
                          {paper.status === "error" && (
                            <span className="text-red-400">{paper.error}</span>
                          )}
                        </span>
                      </div>
                      {paper.status === "extracting" && paper.currentStep && (
                        <div className="mt-1 ml-8">
                          <span className="text-xs text-blue-400 animate-pulse">
                            {paper.currentStep}
                          </span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Go to Analysis button */}
            {completedCount > 0 && (
              <div className="text-center pt-4">
                <button
                  onClick={() => setActiveTab("analysis")}
                  className="px-6 py-3 rounded-lg bg-green-600 hover:bg-green-500 font-medium transition-colors"
                >
                  View Analysis Results ({completedCount} article{completedCount > 1 ? "s" : ""})
                </button>
              </div>
            )}
          </div>
        </main>
      )}

      {/* ── Analysis Tab ── */}
      {activeTab === "analysis" && (
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-5xl mx-auto">
            {analysisData.length === 0 ? (
              <div className="text-center py-20">
                <p className="text-gray-500 text-lg">
                  No articles analyzed yet.
                </p>
                <button
                  onClick={() => setActiveTab("upload")}
                  className="mt-4 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 font-medium text-sm transition-colors"
                >
                  Upload articles
                </button>
              </div>
            ) : (
              <>
                <div className="mb-6">
                  <h2 className="text-xl font-bold text-gray-100">
                    Article Analysis
                  </h2>
                  <p className="text-sm text-gray-500 mt-1">
                    {analysisData.length} article{analysisData.length > 1 ? "s" : ""} analyzed. Scores from evaluation modules shown below.
                  </p>
                </div>
                <ArticleRankingTable articles={analysisData} />
              </>
            )}
          </div>
        </main>
      )}
    </div>
  );
}
