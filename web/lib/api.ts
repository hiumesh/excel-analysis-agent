interface ReportIQConfig {
  apiUrl?: string;
}

declare global {
  interface Window {
    REPORTIQ_CONFIG?: ReportIQConfig;
  }
}

// Point directly to the backend to bypass Next.js proxy timeouts on long-running streams (SSE)
const getApiBase = () => {
  const PROD_URL = "http://localhost:8000";

  // 1. Check for runtime override (useful for embedded widgets in SharePoint/etc)
  if (typeof window !== "undefined" && window.REPORTIQ_CONFIG?.apiUrl) {
    return `${window.REPORTIQ_CONFIG.apiUrl}/api`;
  }

  // 2. Build-time environment variable (Vite defines this)
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (
    envUrl &&
    envUrl !== "http://localhost:8000" &&
    envUrl !== "http://localhost:3000"
  ) {
    return `${envUrl}/api`;
  }

  // 3. Smart Origin Detection: If we are running on a server (not localhost), use the current origin
  if (
    typeof window !== "undefined" &&
    !window.location.hostname.includes("localhost")
  ) {
    // If we're on the production domain itself, use relative /api
    if (window.location.origin === PROD_URL) {
      return "/api";
    }
    // Otherwise fallback to the hardcoded prod URL
    return `${PROD_URL}/api`;
  }

  // 4. Fallback for Local Development
  return "http://localhost:8000/api";
};

const API_BASE = getApiBase();

export interface UploadResult {
  success: boolean;
  file_path: string;
  filename: string;
}

export interface StreamEvent {
  node?: string;
  is_subgraph?: boolean;
  update?: {
    messages?: Array<{
      type: string;
      content: string;
      tool_calls?: Array<{ name: string; args: Record<string, unknown> }>;
    }>;
    artifacts?: Artifact[];
    final_analysis?: string;
    route_decision?: { reasoning?: string; [key: string]: unknown };
    supervisor_decision?: { reasoning?: string; [key: string]: unknown };
    analysis_plan?: string;
    [key: string]: unknown;
  };
  thread_id?: string;
  status?: string;
  error?: string;
}

export interface Artifact {
  type: string;
  content: string;
  title?: string;
  url?: string;
}

export async function uploadFile(file: File): Promise<UploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Upload failed" }));
    throw new Error(error.detail || "Upload failed");
  }

  return response.json();
}

export async function uploadDefaultFile(file: File): Promise<UploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/upload-default`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Upload failed" }));
    throw new Error(error.detail || "Upload failed");
  }

  return response.json();
}

export async function streamAnalysis(
  query: string,
  filePath: string | null,
  threadId: string | null,
  onEvent: (event: StreamEvent) => void,
  onDone: () => void,
  onError: (error: string) => void,
): Promise<AbortController> {
  const controller = new AbortController();

  try {
    const response = await fetch(`${API_BASE}/analyze/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        file_path: filePath,
        thread_id: threadId,
        email: typeof window !== "undefined" ? (window as any).__USER_EMAIL__ : undefined,
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Analysis failed" }));
      onError(error.detail || "Analysis failed");
      return controller;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      onError("No response stream available");
      return controller;
    }

    const decoder = new TextDecoder();
    let buffer = "";

    const processStream = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith("data: ")) {
              const jsonStr = trimmed.slice(6);
              try {
                const event: StreamEvent = JSON.parse(jsonStr);
                onEvent(event);
              } catch {
                // Skip malformed JSON
              }
            }
          }
        }
        onDone();
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          onError((err as Error).message || "Stream error");
        }
      }
    };

    processStream();
  } catch (err) {
    if ((err as Error).name !== "AbortError") {
      onError((err as Error).message || "Connection failed");
    }
  }

  return controller;
}
