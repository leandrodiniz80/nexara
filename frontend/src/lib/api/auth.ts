import { apiClient, toApiClientError } from "@/lib/api/client";
import type { ApiResponse, LoginRequest, MeResponse, SessionResponse } from "@/lib/api/types";

/** POST /api/v1/auth/login — backend/app/api/routers/auth.py */
export async function login(body: LoginRequest): Promise<SessionResponse> {
  try {
    const { data } = await apiClient.post<ApiResponse<SessionResponse>>("/auth/login", body);
    if (!data.data) {
      throw new Error("Login succeeded but no session was returned");
    }
    return data.data;
  } catch (error) {
    throw toApiClientError(error);
  }
}

/** POST /api/v1/auth/logout — requires the current bearer token */
export async function logout(): Promise<void> {
  try {
    await apiClient.post<ApiResponse<null>>("/auth/logout");
  } catch (error) {
    throw toApiClientError(error);
  }
}

/** GET /api/v1/auth/me — resolves the session behind the current bearer token */
export async function me(): Promise<MeResponse> {
  try {
    const { data } = await apiClient.get<ApiResponse<MeResponse>>("/auth/me");
    if (!data.data) {
      throw new Error("Session check succeeded but no user was returned");
    }
    return data.data;
  } catch (error) {
    throw toApiClientError(error);
  }
}
