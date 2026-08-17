import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { uploadDocument } from "../api/documents";
import { getErrorMessage } from "../api/errors";

/** Single hidden <input type="file"> triggered by a styled label — the
 * simplest reliable cross-browser way to restyle a file picker. */
export function UploadPanel({ onUploaded }) {
  const [error, setError] = useState(null);
  const inputRef = useRef(null);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: uploadDocument,
    onSuccess: (data) => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      onUploaded(data.document_id);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  function handleChange(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setError(null);
    mutation.mutate(file);
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm shadow-slate-200/50">
      <h2 className="text-sm font-semibold text-slate-900">Upload a document</h2>
      <p className="mt-0.5 text-xs text-slate-500">PDF or DOCX, up to 20MB.</p>
      <label
        className={`mt-3 flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-3 py-7 text-center text-sm transition-colors ${
          mutation.isPending
            ? "cursor-not-allowed border-slate-200 text-slate-400"
            : "cursor-pointer border-slate-300 text-slate-500 hover:border-indigo-400 hover:bg-indigo-50/40 hover:text-indigo-600"
        }`}
      >
        <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6" aria-hidden="true">
          <path
            d="M12 16V4m0 0-4 4m4-4 4 4"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M4 16v2.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V16"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span>{mutation.isPending ? "Uploading…" : "Choose a file"}</span>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          className="hidden"
          disabled={mutation.isPending}
          onChange={handleChange}
        />
      </label>
      {error ? (
        <p className="mt-2 rounded-md bg-rose-50 px-2 py-1.5 text-xs text-rose-600">{error}</p>
      ) : null}
    </div>
  );
}
