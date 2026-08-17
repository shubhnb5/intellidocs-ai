import { apiClient } from "./client";

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post(
    "/api/documents/upload",
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

export async function listDocuments() {
  const { data } = await apiClient.get("/api/documents");
  return data.documents;
}

export async function getDocument(documentId) {
  const { data } = await apiClient.get(`/api/documents/${documentId}`);
  return data;
}
