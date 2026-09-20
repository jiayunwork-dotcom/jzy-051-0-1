import type {
  CustomTemplate,
  Formula,
  PaletteCategory,
  PreviewResponse,
  RenderResponse,
  Workspace,
} from "./types";

const API_BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = (await res.json()).detail;
    } catch {
      /* ignore empty body */
    }
    const message =
      typeof detail === "string"
        ? detail
        : detail && typeof detail === "object" && "message" in detail
          ? String((detail as { message: unknown }).message)
          : `请求失败 (${res.status})`;
    const err = new Error(message) as Error & {
      status: number;
      currentVersion?: number;
    };
    err.status = res.status;
    if (detail && typeof detail === "object" && "currentVersion" in detail) {
      err.currentVersion = Number(
        (detail as { currentVersion: unknown }).currentVersion
      );
    }
    throw err;
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  render(source: string, tolerant = true): Promise<RenderResponse> {
    return request("/render", {
      method: "POST",
      body: JSON.stringify({ source, tolerant }),
    });
  },

  preview(formulas: Formula[], tolerant = true): Promise<PreviewResponse> {
    return request("/preview", {
      method: "POST",
      body: JSON.stringify({ formulas, tolerant }),
    });
  },

  palette(): Promise<{ categories: PaletteCategory[] }> {
    return request("/palette");
  },

  listWorkspaces(): Promise<Workspace[]> {
    return request("/workspaces");
  },

  getWorkspace(id: string): Promise<Workspace> {
    return request(`/workspaces/${encodeURIComponent(id)}`);
  },

  createWorkspace(
    name: string,
    formulas: Formula[],
    templates: CustomTemplate[]
  ): Promise<Workspace> {
    return request("/workspaces", {
      method: "POST",
      body: JSON.stringify({ name, formulas, templates }),
    });
  },

  saveWorkspace(
    id: string,
    name: string,
    expectedVersion: number,
    formulas: Formula[],
    templates: CustomTemplate[]
  ): Promise<Workspace> {
    return request(`/workspaces/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify({
        name,
        expectedVersion,
        formulas,
        templates,
      }),
    });
  },

  deleteWorkspace(id: string): Promise<void> {
    return request(`/workspaces/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },
};
