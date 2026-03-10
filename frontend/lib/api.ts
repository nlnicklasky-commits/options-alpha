/**
 * API client — uses relative "/api" paths so Next.js rewrites proxy
 * all requests to the backend. This avoids CORS entirely in production.
 *
 * In local dev, next.config.ts rewrites /api/* → http://localhost:8000/api/*
 * In production (Vercel), next.config.ts rewrites /api/* → $BACKEND_URL/api/*
 */

interface FetchOptions extends RequestInit {
  params?: Record<string, string>;
}

export async function api<T>(
  path: string,
  options: FetchOptions = {}
): Promise<T> {
  const { params, ...fetchOptions } = options;

  // Always use relative path — Next.js rewrites handle proxying
  let url = path;
  if (params) {
    const searchParams = new URLSearchParams(params);
    url += `?${searchParams.toString()}`;
  }

  const response = await fetch(url, {
    ...fetchOptions,
    headers: {
      "Content-Type": "application/json",
      ...fetchOptions.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}
