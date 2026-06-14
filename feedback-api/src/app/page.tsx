"use client";

import { useEffect, useState, useCallback } from "react";

// ── Types ──────────────────────────────────────────────────────────

interface FeedbackSummary {
  totalCount: number;
  averageRating: number;
  ratingDistribution: Record<string, number>;
  categoryCounts: Record<string, number>;
  topTags: { tag: string; count: number }[];
  recentCount7d: number;
}

interface Feedback {
  id: string;
  text: string;
  rating: number;
  category: string;
  author: string;
  created_at: string;
  tags: string[];
}

// ── Helpers ────────────────────────────────────────────────────────

function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffDay > 0) return `${diffDay}d ago`;
  if (diffHr > 0) return `${diffHr}h ago`;
  if (diffMin > 0) return `${diffMin}m ago`;
  return "just now";
}

function Stars({ rating }: { rating: number }) {
  return (
    <span className="inline-flex gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <span
          key={i}
          className={i <= rating ? "text-yellow-400" : "text-gray-600"}
        >
          ★
        </span>
      ))}
    </span>
  );
}

const CATEGORY_COLORS: Record<string, string> = {
  ui: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  performance: "bg-orange-500/20 text-orange-300 border-orange-500/30",
  bug: "bg-red-500/20 text-red-300 border-red-500/30",
  feature: "bg-green-500/20 text-green-300 border-green-500/30",
  documentation: "bg-purple-500/20 text-purple-300 border-purple-500/30",
};

function categoryColor(cat: string): string {
  return (
    CATEGORY_COLORS[cat] ||
    "bg-gray-500/20 text-gray-300 border-gray-500/30"
  );
}

// ── Component ──────────────────────────────────────────────────────

export default function Dashboard() {
  const [summary, setSummary] = useState<FeedbackSummary | null>(null);
  const [recentFeedback, setRecentFeedback] = useState<Feedback[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [summaryRes, feedbackRes] = await Promise.all([
        fetch("/api/feedback/summary"),
        fetch("/api/feedback?sort=newest&limit=5"),
      ]);

      if (!summaryRes.ok || !feedbackRes.ok) {
        throw new Error("Failed to fetch data");
      }

      const summaryData = await summaryRes.json();
      const feedbackData = await feedbackRes.json();

      setSummary(summaryData);
      setRecentFeedback(feedbackData.items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-gray-400 text-lg">Loading dashboard...</div>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-red-400 text-lg">
          Error: {error || "No data available"}
        </div>
      </div>
    );
  }

  const maxRatingCount = Math.max(
    ...Object.values(summary.ratingDistribution),
    1
  );

  const maxTagCount = Math.max(...summary.topTags.map((t) => t.count), 1);
  const minTagCount = Math.min(...summary.topTags.map((t) => t.count), 1);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white">
            Feedback Dashboard
          </h1>
          <p className="text-gray-400 mt-1">
            Real-time analytics &middot; auto-refreshes every 30s
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          {/* Total Count */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <p className="text-sm text-gray-400 uppercase tracking-wide">
              Total Feedback
            </p>
            <p className="text-5xl font-bold text-white mt-2">
              {summary.totalCount}
            </p>
            <p className="text-sm text-gray-500 mt-2">
              {summary.recentCount7d} in the last 7 days
            </p>
          </div>

          {/* Average Rating */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <p className="text-sm text-gray-400 uppercase tracking-wide">
              Average Rating
            </p>
            <p className="text-5xl font-bold text-white mt-2">
              {summary.averageRating.toFixed(1)}
            </p>
            <div className="mt-2 text-2xl">
              <Stars rating={Math.round(summary.averageRating)} />
            </div>
          </div>

          {/* Recent 7d */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <p className="text-sm text-gray-400 uppercase tracking-wide">
              Last 7 Days
            </p>
            <p className="text-5xl font-bold text-white mt-2">
              {summary.recentCount7d}
            </p>
            <p className="text-sm text-gray-500 mt-2">
              new feedback entries
            </p>
          </div>
        </div>

        {/* Main Grid: Rating Distribution + Category Breakdown */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
          {/* Rating Distribution */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-white mb-4">
              Rating Distribution
            </h2>
            <div className="space-y-3">
              {[5, 4, 3, 2, 1].map((rating) => {
                const count =
                  summary.ratingDistribution[String(rating)] || 0;
                const pct = (count / maxRatingCount) * 100;
                return (
                  <div key={rating} className="flex items-center gap-3">
                    <span className="w-8 text-sm text-gray-400 text-right">
                      {rating}★
                    </span>
                    <div className="flex-1 h-6 bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-yellow-500 rounded-full transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="w-8 text-sm text-gray-400">
                      {count}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Category Breakdown */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-white mb-4">
              Categories
            </h2>
            <div className="flex flex-wrap gap-2">
              {Object.entries(summary.categoryCounts).map(
                ([category, count]) => (
                  <span
                    key={category}
                    className={`inline-flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-medium ${categoryColor(category)}`}
                  >
                    {category}
                    <span className="bg-white/10 rounded-full px-2 py-0.5 text-xs">
                      {count}
                    </span>
                  </span>
                )
              )}
            </div>
          </div>
        </div>

        {/* Tag Cloud + Recent Feedback */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Top Tags */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-white mb-4">
              Top Tags
            </h2>
            <div className="flex flex-wrap gap-2 items-center">
              {summary.topTags.map(({ tag, count }) => {
                const range = maxTagCount - minTagCount || 1;
                const normalized = (count - minTagCount) / range;
                const fontSize = 0.75 + normalized * 1.25; // 0.75rem to 2rem
                return (
                  <span
                    key={tag}
                    className="text-blue-400 hover:text-blue-300 transition-colors cursor-default"
                    style={{ fontSize: `${fontSize}rem` }}
                    title={`${tag}: ${count}`}
                  >
                    {tag}
                  </span>
                );
              })}
            </div>
          </div>

          {/* Recent Feedback */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-white mb-4">
              Recent Feedback
            </h2>
            <div className="space-y-4">
              {recentFeedback.map((fb) => (
                <div
                  key={fb.id}
                  className="border-b border-gray-800 pb-4 last:border-0 last:pb-0"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm text-gray-300 line-clamp-2 flex-1">
                      {fb.text}
                    </p>
                    <span className="text-xs text-gray-500 whitespace-nowrap">
                      {relativeTime(fb.created_at)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <Stars rating={fb.rating} />
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full border ${categoryColor(fb.category)}`}
                    >
                      {fb.category}
                    </span>
                    <span className="text-xs text-gray-500">
                      {fb.author}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
