"use client";

import { useState } from "react";
import useSWR from "swr";
import { apiFetch } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface SuggestionCard {
  id: string;
  rank: number;
  strategy: string;
  preview_text: string;
  full_text: string;
}

interface SuggestionListResponse {
  lead_id: string;
  suggestions: SuggestionCard[];
  ready: boolean;
}

interface SuggestionPanelProps {
  leadId: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const STRATEGY_LABELS: Record<string, string> = {
  discovery: "Discovery",
  value_proposition: "Value Proposition",
  social_proof: "Social Proof",
  urgency: "Urgency",
  negotiation: "Negotiation",
};

// ── Component ─────────────────────────────────────────────────────────────────

export function SuggestionPanel({ leadId }: SuggestionPanelProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const { data, error, isLoading } = useSWR<SuggestionListResponse>(
    `/api/v1/suggestions/${leadId}`,
    (path: string) => apiFetch<SuggestionListResponse>(path),
    { refreshInterval: data => (data?.ready ? 0 : 2000) }
  );

  async function handleCopy(text: string, id: string) {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  async function handleSelect(suggestionId: string) {
    await apiFetch(`/api/v1/suggestions/${suggestionId}/select`, {
      method: "POST",
      body: {},
    });
  }

  if (isLoading) {
    return <p className="p-4 text-sm text-gray-500">Generating suggestions…</p>;
  }
  if (error) {
    return <p className="p-4 text-sm text-red-500">Failed to load suggestions.</p>;
  }
  if (!data?.ready) {
    return <p className="p-4 text-sm text-gray-500">Pipeline running…</p>;
  }

  return (
    <div className="space-y-3">
      {data.suggestions.map((s) => (
        <div
          key={s.id}
          className="p-4 bg-white border border-gray-200 rounded-lg"
        >
          {/* Header: rank badge + strategy label */}
          <div className="flex items-center gap-2 mb-2">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold shrink-0">
              {s.rank}
            </span>
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              {STRATEGY_LABELS[s.strategy] ?? s.strategy}
            </span>
          </div>

          {/* Preview text — first 80 chars */}
          <p className="text-sm text-gray-800 mb-3 leading-relaxed">
            {s.preview_text.length > 80
              ? `${s.preview_text.slice(0, 80)}…`
              : s.preview_text}
          </p>

          {/* Actions */}
          <div className="flex gap-2">
            <button
              onClick={() => handleCopy(s.full_text, s.id)}
              className="px-3 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50 transition-colors"
            >
              {copiedId === s.id ? "Copied!" : "Copy"}
            </button>
            <button
              onClick={() => handleSelect(s.id)}
              className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
            >
              Use this reply
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
