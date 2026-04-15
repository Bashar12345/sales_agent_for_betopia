"use client";

import useSWR from "swr";
import { apiFetch } from "@/lib/api";

interface Lead {
  id: string;
  buyer_name: string;
  status: string;
  created_at: string;
}

function fetcher(path: string) {
  return apiFetch<Lead[]>(path);
}

export default function LeadsPage() {
  const { data: leads, error, isLoading } = useSWR("/api/v1/leads", fetcher);

  return (
    <main className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Leads</h1>

      {isLoading && (
        <p className="text-sm text-gray-500">Loading leads…</p>
      )}

      {error && (
        <p className="text-sm text-red-600">Failed to load leads.</p>
      )}

      {leads && leads.length === 0 && (
        <p className="text-sm text-gray-500">No leads yet.</p>
      )}

      {leads && leads.length > 0 && (
        <ul className="space-y-2">
          {leads.map((lead) => (
            <li
              key={lead.id}
              className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-lg"
            >
              <span className="font-medium">{lead.buyer_name}</span>
              <span className="text-xs text-gray-500 uppercase tracking-wide">
                {lead.status}
              </span>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
