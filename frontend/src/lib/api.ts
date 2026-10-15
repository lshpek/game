/** Typed HTTP client. All game authority lives on the server. */

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL as string | undefined
)?.trim().replace(/\/+$/, '') ?? '';

const TOKEN_STORAGE_KEY = 'numora.token';

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(
    code: string,
    message: string,
    status: number,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

interface ErrorEnvelope {
  success: false;
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export function getToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {
    // Storage may be unavailable in private or restricted WebViews.
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  idempotencyKey?: string;
  signal?: AbortSignal;
  authenticated?: boolean;
}

function buildUrl(
  path: string,
  query?: RequestOptions['query'],
): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const url = `${API_BASE}${normalizedPath}`;

  if (!query) return url;

  const search = new URLSearchParams();

  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') {
      search.set(key, String(value));
    }
  }

  const queryString = search.toString();
  return queryString ? `${url}?${queryString}` : url;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const {
    method = 'GET',
    body,
    query,
    idempotencyKey,
    signal,
    authenticated = true,
  } = options;

  if (!API_BASE) {
    throw new ApiError(
      'API_BASE_URL_MISSING',
      'API server URL is not configured. Set VITE_API_BASE_URL and rebuild the frontend.',
      0,
    );
  }

  const headers: Record<string, string> = {
    Accept: 'application/json',
  };

  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  if (idempotencyKey) {
    headers['Idempotency-Key'] = idempotencyKey;
  }

  if (authenticated) {
    const token = getToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  let response: Response;

  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error;
    }

    throw new ApiError(
      'NETWORK_ERROR',
      'Cannot reach the API server. Check the API URL, server status, and CORS configuration.',
      0,
      {
        url: buildUrl(path, query),
        cause: String(error),
      },
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  let payload: unknown = null;
  const raw = await response.text();

  if (raw) {
    try {
      payload = JSON.parse(raw);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const envelope = payload as ErrorEnvelope | null;
    // HTTP failures are reported with the server's own code and status - never as a
    // network error, because the request did reach the API.
    throw new ApiError(
      envelope?.error?.code ?? 'HTTP_ERROR',
      envelope?.error?.message ?? `Request failed with status ${response.status}.`,
      response.status,
      envelope?.error?.details ?? {},
    );
  }

  return payload as T;
}

/** Stable key so a retried request is deduplicated server side. */
export function makeIdempotencyKey(prefix: string): string {
  const random =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

  return `${prefix}-${random}`;
}
