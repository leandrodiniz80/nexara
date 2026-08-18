import { apiClient, ApiClientError, toApiClientError } from "@/lib/api/client";
import type {
  ApiResponse,
  LoginRequest,
  MeResponse,
  RegisterRequest,
  SessionResponse,
} from "@/lib/api/types";

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

/** POST /api/v1/auth/register — backend/app/api/routers/auth.py */
export async function register(body: RegisterRequest): Promise<void> {
  try {
    await apiClient.post<ApiResponse<null>>("/auth/register", body);
  } catch (error) {
    throw toApiClientError(error);
  }
}

/**
 * Registers a new account and logs it in; if the email is already
 * registered (409), falls back to logging in with the given credentials
 * instead. Any other registration failure propagates normally.
 */
export async function registerOrLogin(email: string, password: string): Promise<SessionResponse> {
  try {
    await register({ email, password });
  } catch (error) {
    // register() above already throws an ApiClientError (not a raw Axios
    // error) — re-running toApiClientError() on it here would fail
    // axios.isAxiosError()'s check and silently reset .status to null,
    // making this 409 check never match. Check the already-wrapped error
    // directly instead.
    if (!(error instanceof ApiClientError) || error.status !== 409) {
      throw error;
    }
  }

  return login({ email, password });
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
