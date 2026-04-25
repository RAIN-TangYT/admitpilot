import type {
  AdmitPilotRequest,
  CurrentUserResponse,
  CatalogResponse,
  LoginResponse,
  RunDetailResponse,
  RunHistoryResponse,
  OrchestrationSocketEvent,
  OrchestrationResponse
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function requestJson<T>(
  path: string,
  init?: RequestInit,
  token?: string
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `API request failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchCatalog(): Promise<CatalogResponse> {
  return requestJson<CatalogResponse>("/api/v1/catalog");
}

export function fetchDemoProfile(): Promise<AdmitPilotRequest> {
  return requestJson<AdmitPilotRequest>("/api/v1/demo-profile");
}

export function runOrchestration(
  payload: AdmitPilotRequest,
  token: string
): Promise<OrchestrationResponse> {
  return requestJson<OrchestrationResponse>(
    "/api/v1/orchestrations",
    {
      method: "POST",
      body: JSON.stringify(payload)
    },
    token
  );
}

export function runOrchestrationSocket({
  onEvent,
  payload,
  token
}: {
  onEvent: (event: OrchestrationSocketEvent) => void;
  payload: AdmitPilotRequest;
  token: string;
}): Promise<OrchestrationResponse> {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(orchestrationSocketUrl(token));
    let settled = false;

    socket.addEventListener("open", () => {
      socket.send(JSON.stringify(payload));
    });

    socket.addEventListener("message", (message) => {
      const event = JSON.parse(String(message.data)) as OrchestrationSocketEvent;
      onEvent(event);
      if (event.event === "workflow_completed") {
        settled = true;
        resolve(event.data.response);
        socket.close();
      }
      if (event.event === "workflow_failed") {
        settled = true;
        reject(new Error(event.data.summary));
        socket.close();
      }
    });

    socket.addEventListener("error", () => {
      if (!settled) {
        settled = true;
        reject(new Error("WebSocket orchestration failed"));
      }
    });

    socket.addEventListener("close", () => {
      if (!settled) {
        settled = true;
        reject(new Error("WebSocket orchestration closed before completion"));
      }
    });
  });
}

export function login(email: string, password: string): Promise<LoginResponse> {
  return requestJson<LoginResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
}

export function fetchCurrentUser(token: string): Promise<CurrentUserResponse> {
  return requestJson<CurrentUserResponse>("/api/v1/auth/me", undefined, token);
}

export function logout(token: string): Promise<{ status: string }> {
  return requestJson<{ status: string }>(
    "/api/v1/auth/logout",
    { method: "POST" },
    token
  );
}

export function fetchRunHistory(token: string): Promise<RunHistoryResponse> {
  return requestJson<RunHistoryResponse>("/api/v1/runs", undefined, token);
}

export function fetchRunDetail(
  token: string,
  runId: string
): Promise<RunDetailResponse> {
  return requestJson<RunDetailResponse>(`/api/v1/runs/${runId}`, undefined, token);
}

export function deleteRun(
  token: string,
  runId: string
): Promise<{ status: string; run_id: string }> {
  return requestJson<{ status: string; run_id: string }>(
    `/api/v1/runs/${runId}`,
    { method: "DELETE" },
    token
  );
}

function orchestrationSocketUrl(token: string): string {
  const url = new URL("/api/v1/orchestrations/ws", API_BASE_URL);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.searchParams.set("token", token);
  return url.toString();
}
