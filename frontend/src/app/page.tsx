"use client";

import { useState, useRef, useCallback, useEffect } from "react";

// --- Types matching backend response ---

interface Metadata {
  title: string;
  authors: string[];
  institutions: string[];
  journal: string | null;
  date: string | null;
}

interface VisualAsset {
  page_number: number;
  width: number;
  height: number;
  image_data: string;
  type: string;
}

interface DatasetLink {
  url: string;
  source: string;
  context: string;
}

interface PaperEntry {
  paper_id: string;
  status: "extracting" | "complete";
  metadata: Metadata | null;
  content: string | null;
  skipped_pages: number[];
  research_methods: string | null;
  dataset_links: DatasetLink[];
  visual_assets: VisualAsset[];
}

// --- Constants ---

const API_BASE = "http://localhost:8000/api";
const POLL_INTERVAL = 2000;
const CONTENT_PREVIEW_LENGTH = 500;

// --- Component ---

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [paperId, setPaperId] = useState<string | null>(null);
  const [status, setStatus] = useState<
    "idle" | "uploading" | "extracting" | "complete" | "error"
  >("idle");
  const [error, setError] = useState<string | null>(null);
  const [paper, setPaper] = useState<PaperEntry | null>(null);
  const [contentExpanded, setContentExpanded] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // --- Polling ---

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startPolling = useCallback(
    (id: string) => {
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/papers/${id}`);
          if (!res.ok) {
            const data = await res.json();
            setError(data.error || "Failed to retrieve paper status");
            setStatus("error");
            stopPolling();
            return;
          }
          const data: PaperEntry = await res.json();
          setPaper(data);
          if (data.status === "complete") {
            setStatus("complete");
            stopPolling();
          }
        } catch {
          setError("Network error while polling for results");
          setStatus("error");
          stopPolling();
        }
      }, POLL_INTERVAL);
    },
    [stopPolling]
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  // --- Upload ---

  const uploadFile = async (selectedFile: File) => {
    setFile(selectedFile);
    setError(null);
    setPaper(null);
    setContentExpanded(false);
    setStatus("uploading");

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const res = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "Upload failed");
        setStatus("error");
        return;
      }

      const id = data.paper_id;
      setPaperId(id);
      setStatus("extracting");
      startPolling(id);
    } catch {
      setError("Network error — is the backend running?");
      setStatus("error");
    }
  };

  // --- Drag & Drop ---

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && dropped.type === "application/pdf") {
      uploadFile(dropped);
    } else {
      setError("Please upload a PDF file");
      setStatus("error");
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      uploadFile(selected);
    }
  };

  // --- Reset ---

  const handleReset = () => {
    stopPolling();
    setFile(null);
    setPaperId(null);
    setStatus("idle");
    setError(null);
    setPaper(null);
    setContentExpanded(false);
  };

  // --- Render helpers ---

  const pageCount = paper?.visual_assets?.length || 0;
  const contentPreview = paper?.content
    ? contentExpanded
      ? paper.content
      : paper.content.slice(0, CONTENT_PREVIEW_LENGTH)
    : null;
  const contentIsTruncated =
    paper?.content != null && paper.content.length > CONTENT_PREVIEW_LENGTH;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800/60 px-6 py-4 backdrop-blur-sm bg-gray-950/80 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-sm font-bold">
              F
            </div>
            <h1 className="text-lg font-semibold tracking-tight">Foldr</h1>
            <span className="text-xs text-gray-500 border border-gray-800 rounded-full px-2 py-0.5">
              Research AI
            </span>
          </div>
          {status !== "idle" && (
            <button
              onClick={handleReset}
              className="text-sm text-gray-400 hover:text-white transition-colors flex items-center gap-1.5"
            >
              <svg
                className="w-3.5 h-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 4v16m8-8H4"
                />
              </svg>
              New analysis
            </button>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 flex flex-col items-center justify-start px-6 py-12">
        <div className="w-full max-w-5xl space-y-8">
          {/* Upload Area — shown when idle or error with no paper */}
          {(status === "idle" || (status === "error" && !paper)) && (
            <div className="space-y-6">
              <div className="text-center space-y-3 mb-10">
                <h2 className="text-3xl font-bold text-gray-50 tracking-tight">
                  Academic Paper Critic
                </h2>
                <p className="text-gray-400 max-w-lg mx-auto">
                  Upload a PDF paper and we&apos;ll extract its metadata,
                  content, and research methods in seconds.
                </p>
              </div>

              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`relative border-2 border-dashed rounded-2xl p-16 text-center cursor-pointer transition-all duration-300 group ${
                  isDragging
                    ? "border-blue-500 bg-blue-500/5 scale-[1.01] shadow-lg shadow-blue-500/10"
                    : "border-gray-700/60 hover:border-gray-500 hover:bg-gray-900/40"
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,application/pdf"
                  onChange={handleFileSelect}
                  className="hidden"
                  aria-label="Upload PDF file"
                />
                <div className="space-y-4">
                  <div className="w-16 h-16 mx-auto rounded-2xl bg-gray-800/80 border border-gray-700/50 flex items-center justify-center group-hover:bg-gray-800 transition-colors">
                    <svg
                      className="w-7 h-7 text-gray-400 group-hover:text-gray-300 transition-colors"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={1.5}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
                      />
                    </svg>
                  </div>
                  <div>
                    <p className="text-gray-200 font-medium text-lg">
                      Drop your PDF here
                    </p>
                    <p className="text-gray-500 text-sm mt-1">
                      or click to browse · PDF files up to 20 MB
                    </p>
                  </div>
                </div>
              </div>

              {/* Error message */}
              {error && (
                <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-5 py-4 text-red-400 text-sm flex items-center gap-3">
                  <svg
                    className="w-5 h-5 flex-shrink-0"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                    />
                  </svg>
                  {error}
                </div>
              )}
            </div>
          )}

          {/* Uploading state */}
          {status === "uploading" && (
            <StatusCard
              title="Uploading..."
              subtitle={file?.name || "Sending file to server"}
              variant="loading"
            />
          )}

          {/* Extracting state */}
          {status === "extracting" && (
            <StatusCard
              title="Extracting..."
              subtitle="Analyzing your paper — parsing metadata, content, and research methods"
              variant="loading"
            />
          )}

          {/* Complete state — results dashboard */}
          {status === "complete" && paper && (
            <div className="space-y-6 animate-in fade-in duration-500">
              {/* Success banner */}
              <div className="rounded-xl bg-gradient-to-r from-green-500/10 to-emerald-500/5 border border-green-500/20 px-6 py-5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center">
                    <svg
                      className="w-5 h-5 text-green-400"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M4.5 12.75l6 6 9-13.5"
                      />
                    </svg>
                  </div>
                  <div>
                    <p className="text-green-400 font-medium">
                      Extraction complete
                    </p>
                    <p className="text-green-400/60 text-sm">
                      All data extracted successfully
                    </p>
                  </div>
                </div>
                {/* Stats pills */}
                <div className="flex items-center gap-3">
                  <StatPill
                    label="Pages"
                    value={pageCount.toString()}
                  />
                  <StatPill
                    label="Visual Assets"
                    value={(paper.visual_assets?.length || 0).toString()}
                  />
                  {paper.skipped_pages.length > 0 && (
                    <StatPill
                      label="Skipped"
                      value={paper.skipped_pages.length.toString()}
                      variant="warning"
                    />
                  )}
                </div>
              </div>

              {/* Metadata */}
              {paper.metadata && (
                <DashboardSection title="Paper Metadata" icon="metadata">
                  <div className="space-y-4">
                    <h4 className="text-xl font-semibold text-gray-50 leading-tight">
                      {paper.metadata.title}
                    </h4>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {paper.metadata.authors.length > 0 && (
                        <MetadataField
                          label="Authors"
                          value={paper.metadata.authors.join(", ")}
                        />
                      )}
                      {paper.metadata.institutions.length > 0 && (
                        <MetadataField
                          label="Institutions"
                          value={paper.metadata.institutions.join(", ")}
                        />
                      )}
                      {paper.metadata.journal && (
                        <MetadataField
                          label="Journal"
                          value={paper.metadata.journal}
                        />
                      )}
                      {paper.metadata.date && (
                        <MetadataField
                          label="Publication Date"
                          value={paper.metadata.date}
                        />
                      )}
                    </div>
                  </div>
                </DashboardSection>
              )}

              {/* Research Methods */}
              {paper.research_methods && (
                <DashboardSection title="Research Methods" icon="methods">
                  <div className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap max-h-80 overflow-y-auto pr-2 custom-scrollbar">
                    {paper.research_methods}
                  </div>
                </DashboardSection>
              )}

              {/* Dataset Links */}
              {paper.dataset_links && paper.dataset_links.length > 0 && (
                <DashboardSection title="Dataset Links Found" icon="content">
                  <div className="space-y-3">
                    {paper.dataset_links.map((link, i) => (
                      <div
                        key={i}
                        className="rounded-lg bg-gray-800/50 border border-gray-700/40 p-4 space-y-2"
                      >
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-500/15 text-blue-400 border border-blue-500/20">
                            {link.source}
                          </span>
                          <a
                            href={link.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-blue-400 hover:text-blue-300 underline underline-offset-2 truncate max-w-md"
                          >
                            {link.url}
                          </a>
                        </div>
                        <p className="text-xs text-gray-500 italic truncate">
                          &ldquo;...{link.context}...&rdquo;
                        </p>
                      </div>
                    ))}
                  </div>
                </DashboardSection>
              )}

              {/* Content Preview */}
              {contentPreview && (
                <DashboardSection title="Content Preview" icon="content">
                  <div className="text-gray-400 text-sm leading-relaxed whitespace-pre-wrap max-h-72 overflow-y-auto pr-2 custom-scrollbar">
                    {contentPreview}
                    {!contentExpanded && contentIsTruncated && "..."}
                  </div>
                  {contentIsTruncated && (
                    <button
                      onClick={() => setContentExpanded(!contentExpanded)}
                      className="mt-3 text-sm text-blue-400 hover:text-blue-300 transition-colors flex items-center gap-1"
                    >
                      {contentExpanded ? (
                        <>
                          <svg
                            className="w-3.5 h-3.5"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={2}
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M4.5 15.75l7.5-7.5 7.5 7.5"
                            />
                          </svg>
                          Show less
                        </>
                      ) : (
                        <>
                          <svg
                            className="w-3.5 h-3.5"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={2}
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M19.5 8.25l-7.5 7.5-7.5-7.5"
                            />
                          </svg>
                          Show full content
                        </>
                      )}
                    </button>
                  )}
                </DashboardSection>
              )}

              {/* Charts */}
              {paper.visual_assets && paper.visual_assets.filter(a => a.type === 'chart').length > 0 && (
                <DashboardSection title="Charts & Graphs" icon="methods">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-h-[600px] overflow-y-auto pr-2 custom-scrollbar">
                    {paper.visual_assets.filter(a => a.type === 'chart').map((asset, i) => (
                      <div
                        key={i}
                        className="relative group rounded-lg overflow-hidden border border-blue-500/20 bg-white"
                      >
                        <img
                          src={`data:image/png;base64,${asset.image_data}`}
                          alt={`Chart from page ${asset.page_number}`}
                          className="w-full h-auto"
                        />
                        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent px-3 py-2">
                          <span className="text-xs text-white/80 font-medium">
                            Page {asset.page_number}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </DashboardSection>
              )}

              {/* Images */}
              {paper.visual_assets && paper.visual_assets.filter(a => a.type === 'image').length > 0 && (
                <DashboardSection title="Images & Diagrams" icon="content">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-h-[600px] overflow-y-auto pr-2 custom-scrollbar">
                    {paper.visual_assets.filter(a => a.type === 'image').map((asset, i) => (
                      <div
                        key={i}
                        className="relative group rounded-lg overflow-hidden border border-green-500/20 bg-white"
                      >
                        <img
                          src={`data:image/png;base64,${asset.image_data}`}
                          alt={`Image from page ${asset.page_number}`}
                          className="w-full h-auto"
                        />
                        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent px-3 py-2">
                          <span className="text-xs text-white/80 font-medium">
                            Page {asset.page_number}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </DashboardSection>
              )}

              {/* Stats summary */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard
                  label="Total Pages"
                  value={pageCount.toString()}
                  icon="pages"
                />
                <StatCard
                  label="Visual Assets"
                  value={(paper.visual_assets?.length || 0).toString()}
                  icon="images"
                />
                <StatCard
                  label="Skipped Pages"
                  value={paper.skipped_pages.length.toString()}
                  icon="skipped"
                />
                <StatCard
                  label="Methods Found"
                  value={paper.research_methods ? "Yes" : "No"}
                  icon="methods"
                />
              </div>

              {/* No metadata fallback */}
              {!paper.metadata &&
                !paper.content &&
                !paper.research_methods && (
                  <div className="rounded-xl bg-yellow-500/10 border border-yellow-500/20 px-5 py-4 text-yellow-400 text-sm flex items-center gap-3">
                    <svg
                      className="w-5 h-5 flex-shrink-0"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                      />
                    </svg>
                    No extractable content found in this PDF. The file may be
                    image-only or corrupted.
                  </div>
                )}
            </div>
          )}

          {/* Error state with paper loaded */}
          {status === "error" && paper && (
            <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-5 py-4 text-red-400 text-sm flex items-center gap-3">
              <svg
                className="w-5 h-5 flex-shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                />
              </svg>
              {error}
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800/40 px-6 py-3">
        <div className="max-w-5xl mx-auto flex items-center justify-between text-xs text-gray-600">
          <span>Foldr Research AI</span>
          {paperId && (
            <span className="font-mono text-gray-700">
              ID: {paperId.slice(0, 8)}
            </span>
          )}
        </div>
      </footer>
    </div>
  );
}

// --- Sub-components ---

function StatusCard({
  title,
  subtitle,
  variant,
}: {
  title: string;
  subtitle: string;
  variant: "loading" | "success";
}) {
  return (
    <div className="rounded-2xl bg-gray-900/80 border border-gray-800/60 p-10 flex flex-col items-center gap-5 text-center">
      {variant === "loading" && (
        <div className="relative">
          <div className="w-12 h-12 rounded-full border-2 border-gray-700 border-t-blue-500 animate-spin" />
          <div className="absolute inset-0 w-12 h-12 rounded-full border-2 border-transparent border-b-violet-500 animate-spin [animation-duration:1.5s]" />
        </div>
      )}
      <div>
        <p className="text-gray-100 font-semibold text-lg">{title}</p>
        <p className="text-gray-500 text-sm mt-1">{subtitle}</p>
      </div>
    </div>
  );
}

function DashboardSection({
  title,
  icon,
  children,
}: {
  title: string;
  icon: "metadata" | "methods" | "content";
  children: React.ReactNode;
}) {
  const iconMap = {
    metadata: (
      <svg
        className="w-4 h-4"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M15 9h3.75M15 12h3.75M15 15h3.75M4.5 19.5h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5zm6-10.125a1.875 1.875 0 11-3.75 0 1.875 1.875 0 013.75 0zm1.294 6.336a6.721 6.721 0 01-3.17.789 6.721 6.721 0 01-3.168-.789 3.376 3.376 0 016.338 0z"
        />
      </svg>
    ),
    methods: (
      <svg
        className="w-4 h-4"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5"
        />
      </svg>
    ),
    content: (
      <svg
        className="w-4 h-4"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
        />
      </svg>
    ),
  };

  return (
    <section className="rounded-xl bg-gray-900/60 border border-gray-800/50 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-800/40 flex items-center gap-2">
        <span className="text-gray-400">{iconMap[icon]}</span>
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
          {title}
        </h3>
      </div>
      <div className="px-6 py-5">{children}</div>
    </section>
  );
}

function MetadataField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">
        {label}
      </p>
      <p className="text-gray-300 text-sm">{value}</p>
    </div>
  );
}

function StatPill({
  label,
  value,
  variant = "default",
}: {
  label: string;
  value: string;
  variant?: "default" | "warning";
}) {
  const colors =
    variant === "warning"
      ? "bg-yellow-500/10 border-yellow-500/20 text-yellow-400"
      : "bg-gray-800/60 border-gray-700/50 text-gray-300";

  return (
    <div
      className={`px-3 py-1.5 rounded-lg border text-xs font-medium ${colors}`}
    >
      <span className="text-gray-500 mr-1">{label}:</span>
      {value}
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: "pages" | "images" | "skipped" | "methods";
}) {
  const iconMap = {
    pages: "📄",
    images: "🖼️",
    skipped: "⏭️",
    methods: "🔬",
  };

  return (
    <div className="rounded-xl bg-gray-900/60 border border-gray-800/50 p-4 text-center">
      <div className="text-xl mb-1">{iconMap[icon]}</div>
      <p className="text-2xl font-bold text-gray-100">{value}</p>
      <p className="text-xs text-gray-500 mt-0.5">{label}</p>
    </div>
  );
}
