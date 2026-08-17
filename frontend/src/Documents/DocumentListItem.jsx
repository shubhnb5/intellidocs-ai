import { useQuery } from "@tanstack/react-query";

import { getDocument } from "../api/documents";
import { getErrorMessage } from "../api/errors";

// spaCy's default NER labels, mapped to a color each so scanning a document's
// entity badges reads like a legend rather than a wall of same-colored text.
const ENTITY_LABEL_COLORS = {
  PERSON: "bg-blue-100 text-blue-700",
  ORG: "bg-purple-100 text-purple-700",
  GPE: "bg-emerald-100 text-emerald-700",
  LOC: "bg-emerald-100 text-emerald-700",
  DATE: "bg-amber-100 text-amber-700",
  TIME: "bg-amber-100 text-amber-700",
  MONEY: "bg-green-100 text-green-700",
  PRODUCT: "bg-pink-100 text-pink-700",
  EVENT: "bg-orange-100 text-orange-700",
  NORP: "bg-cyan-100 text-cyan-700",
  LAW: "bg-red-100 text-red-700",
  PERCENT: "bg-lime-100 text-lime-700",
  CARDINAL: "bg-slate-100 text-slate-700",
};
const DEFAULT_ENTITY_COLOR = "bg-slate-100 text-slate-700";

export function DocumentListItem({ doc, expanded, onToggle }) {
  const detailQuery = useQuery({
    queryKey: ["document", doc.document_id],
    queryFn: () => getDocument(doc.document_id),
    enabled: expanded,
  });

  return (
    <li className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm shadow-slate-200/50 transition-shadow hover:shadow-md">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
            <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden="true">
              <path
                d="M7 3.5h7l4 4V19a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19V5A1.5 1.5 0 0 1 7 3.5Z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
              <path
                d="M14 3.5V7a1 1 0 0 0 1 1h3.5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-900">{doc.filename}</p>
            <p className="text-xs text-slate-500">
              {doc.chunk_count} chunk{doc.chunk_count === 1 ? "" : "s"} ·{" "}
              {new Date(doc.uploaded_at).toLocaleString()}
            </p>
          </div>
        </div>
        <svg
          viewBox="0 0 24 24"
          fill="none"
          className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${expanded ? "rotate-180" : ""}`}
          aria-hidden="true"
        >
          <path
            d="m6 9 6 6 6-6"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {expanded ? (
        <div className="border-t border-slate-100 bg-slate-50/60 px-4 py-3">
          {detailQuery.isPending ? (
            <p className="text-xs text-slate-500">Loading details…</p>
          ) : detailQuery.isError ? (
            <p className="text-xs text-rose-600">{getErrorMessage(detailQuery.error)}</p>
          ) : (
            <DocumentDetailBody
              summary={detailQuery.data.summary}
              topics={detailQuery.data.topics}
              entities={detailQuery.data.entities}
            />
          )}
        </div>
      ) : null}
    </li>
  );
}

function DocumentDetailBody({ summary, topics, entities }) {
  return (
    <div className="space-y-3">
      {summary ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            Summary
          </p>
          <p className="mt-1 text-sm text-slate-600">{summary}</p>
        </div>
      ) : null}
      {topics.length > 0 ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            Topics
          </p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {topics.map((topic) => (
              <span
                key={topic}
                className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700"
              >
                {topic}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      {entities.length > 0 ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            Entities
          </p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {entities.map((entity, index) => (
              <span
                key={`${entity.text}-${index}`}
                className={`rounded px-2 py-0.5 text-xs font-medium ${
                  ENTITY_LABEL_COLORS[entity.label] ?? DEFAULT_ENTITY_COLOR
                }`}
                title={entity.label}
              >
                {entity.text}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
