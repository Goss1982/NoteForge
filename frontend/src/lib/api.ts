export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      ...(init.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...init.headers,
    },
  });
  if (!res.ok) {
    const data = await res
      .json()
      .catch(() => ({ detail: `Request failed (${res.status})` }));
    throw new ApiError(
      res.status,
      typeof data.detail === "string"
        ? data.detail
        : "Please check the supplied values.",
    );
  }
  return res.json();
}
