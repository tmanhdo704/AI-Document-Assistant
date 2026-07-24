const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";
const TOKEN_KEY = "docalley-access-token";

type ErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
  };
};

export type User = {
  id: string;
  email: string;
  full_name: string | null;
  auth_provider: string;
  role: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: "bearer";
  user: User;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function saveAccessToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

async function send<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getAccessToken();

  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;

  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
      credentials: "include",
    });
  } catch {
    throw new ApiError(
      "Không thể kết nối đến máy chủ. Vui lòng thử lại.",
      "NETWORK_ERROR",
      0,
    );
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ErrorEnvelope;

    throw new ApiError(
      body.error?.message ?? "Yêu cầu không thành công.",
      body.error?.code ?? "REQUEST_FAILED",
      response.status,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

let refreshPromise: Promise<AuthResponse> | null = null;

async function refreshSession(): Promise<AuthResponse> {
  if (!refreshPromise) {
    refreshPromise = send<AuthResponse>("/auth/refresh", {
      method: "POST",
    })
      .then((response) => {
        saveAccessToken(response.access_token);
        return response;
      })
      .catch((error) => {
        clearAccessToken();
        throw error;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  try {
    return await send<T>(path, options);
  } catch (error) {
    const canRefresh =
      error instanceof ApiError &&
      error.status === 401 &&
      getAccessToken() !== null &&
      path !== "/auth/login" &&
      path !== "/auth/register" &&
      path !== "/auth/google" &&
      path !== "/auth/refresh" &&
      path !== "/auth/logout";

    if (!canRefresh) {
      throw error;
    }

    await refreshSession();

    return send<T>(path, options);
  }
}

export type HealthResponse = {
  status: string;
  service: string;
};

export type GuestUsage = {
  question_count: number;
  question_limit: number;
  questions_remaining: number;
};

export type Document = {
  id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  status: string;
  page_count: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type Citation = {
  index: number;
  document_id: string;
  filename: string;
  page_number: number;
  excerpt: string;
};

export type AnswerResponse = {
  answer: string;
  citations: Citation[];
  questions_remaining: number | null;
};

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function createGuestSession(): Promise<GuestUsage> {
  return request<GuestUsage>("/guest/session", {
    method: "POST",
  });
}

export async function uploadDocument(file: File): Promise<Document> {
  const formData = new FormData();
  formData.append("file", file);

  return request<Document>("/documents", {
    method: "POST",
    body: formData,
  });
}

export async function listDocuments(): Promise<Document[]> {
  return request<Document[]>("/documents");
}

export async function askDocuments(
  question: string,
): Promise<AnswerResponse> {
  return request<AnswerResponse>("/ask", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export async function login(
  email: string,
  password: string,
): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function register(
  email: string,
  password: string,
  fullName: string,
): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
      full_name: fullName.trim() || null,
    }),
  });
}

export async function googleLogin(
  credential: string,
): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/google", {
    method: "POST",
    body: JSON.stringify({ credential }),
  });
}

export async function getCurrentUser(): Promise<User> {
  return request<User>("/auth/me");
}

export async function logout(): Promise<void> {
  try {
    await request<void>("/auth/logout", {
      method: "POST",
    });
  } finally {
    clearAccessToken();
  }
}
