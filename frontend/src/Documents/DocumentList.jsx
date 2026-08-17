import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { listDocuments } from "../api/documents";
import { getErrorMessage } from "../api/errors";
import { DocumentListItem } from "./DocumentListItem";

// autoExpandId is set right after a successful upload so the just-uploaded
// document opens itself instead of the user having to find and click it in
// the list.
export function DocumentList({ autoExpandId }) {
  const [expandedId, setExpandedId] = useState(null);

  const documentsQuery = useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
  });

  useEffect(() => {
    if (autoExpandId) {
      setExpandedId(autoExpandId);
    }
  }, [autoExpandId]);

  if (documentsQuery.isPending) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500 shadow-sm shadow-slate-200/50">
        Loading documents…
      </div>
    );
  }
  if (documentsQuery.isError) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-600">
        {getErrorMessage(documentsQuery.error)}
      </div>
    );
  }
  if (documentsQuery.data.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-200 bg-white p-6 text-center text-sm text-slate-400">
        No documents uploaded yet.
      </div>
    );
  }

  return (
    <ul className="space-y-2.5">
      {documentsQuery.data.map((doc) => (
        <DocumentListItem
          key={doc.document_id}
          doc={doc}
          expanded={expandedId === doc.document_id}
          onToggle={() =>
            setExpandedId((current) => (current === doc.document_id ? null : doc.document_id))
          }
        />
      ))}
    </ul>
  );
}
