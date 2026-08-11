import { apiClient } from "./client";

export interface HealthResponse {
  status: string;
  app_name: string;
  environment: string;
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>("/api/health");
  return data;
}
