import axios from "axios";

import { getToken } from "@/lib/auth/token";

/**
 * NEXT_PUBLIC_API_URL is expected to include the /api/v1 prefix, matching
 * frontend/.env.local.example — every call site below is written relative
 * to that base (e.g. "/auth/login", not "/api/v1/auth/login").
 */
export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * Every Nexara API response — success or failure — is wrapped in the same
 * ApiResponse envelope (backend/app/api/responses/api_response.py).
 * ApiClientError carries the human-readable message straight through so
 * callers don't need to know the envelope shape.
 */
export class ApiClientError extends Error {
  status: number | null;
  code: string | null;

  constructor(message: string, status: number | null, code: string | null) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
  }
}

export function toApiClientError(error: unknown): ApiClientError {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status ?? null;
    const firstError = error.response?.data?.errors?.[0];
    const message = firstError?.message ?? error.message ?? "Request failed";
    const code = firstError?.code ?? null;
    return new ApiClientError(message, status, code);
  }
  return new ApiClientError(error instanceof Error ? error.message : "Unknown error", null, null);
}
