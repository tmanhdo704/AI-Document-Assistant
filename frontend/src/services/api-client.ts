const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export type HealthResponse = {
  status: string;
  service: string;
};

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_URL}/health`);

  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }

  return response.json() as Promise<HealthResponse>;
}
