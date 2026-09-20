const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

function getToken(): string | null {
  return localStorage.getItem("ri_token");
}
export { getToken };

export function setToken(token: string | null) {
  if (token) localStorage.setItem("ri_token", token);
  else localStorage.removeItem("ri_token");
}

export function getRole(): string | null {
  return localStorage.getItem("ri_role");
}

export function setRole(role: string | null) {
  if (role) localStorage.setItem("ri_role", role);
  else localStorage.removeItem("ri_role");
}

async function request(path: string, options: RequestInit = {}) {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> | undefined),
  };
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  const contentType = resp.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return resp.json();
  return resp.blob();
}

export const api = {
  register: (email: string, password: string, role: string) =>
    request("/api/auth/register", { method: "POST", body: JSON.stringify({ email, password, role }) }),
  login: (email: string, password: string) =>
    request("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request("/api/auth/me"),

  listDatasets: () => request("/api/datasets"),
  getDataset: (id: number) => request(`/api/datasets/${id}`),
  getTransformations: (id: number) => request(`/api/datasets/${id}/transformations`),
  getFlagged: (id: number) => request(`/api/datasets/${id}/flagged?limit=25`),
  uploadDataset: (file: File, isDemo: boolean) => {
    const form = new FormData();
    form.append("file", file);
    return request(`/api/datasets/upload?is_demo=${isDemo}`, { method: "POST", body: form });
  },

  trainModel: (datasetId: number, horizon: number) =>
    request(`/api/models/train?dataset_id=${datasetId}&horizon=${horizon}`, { method: "POST" }),
  getForecast: (datasetId: number, storeId: number, itemId: number) =>
    request(`/api/forecast?dataset_id=${datasetId}&store_id=${storeId}&item_id=${itemId}`),
  getFeatureImportance: (datasetId: number) => request(`/api/models/${datasetId}/feature-importance`),

  optimizeInventory: (datasetId: number, params: Record<string, number>) => {
    const qs = new URLSearchParams({ dataset_id: String(datasetId), ...Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])) });
    return request(`/api/inventory/optimize?${qs.toString()}`, { method: "POST" });
  },
  simulateSale: (datasetId: number, storeId: number, itemId: number, quantity: number) =>
    request(`/api/simulation/sale?dataset_id=${datasetId}&store_id=${storeId}&item_id=${itemId}&quantity=${quantity}`, { method: "POST" }),
  getSimulationState: (datasetId: number, storeId: number, itemId: number) =>
    request(`/api/simulation/state?dataset_id=${datasetId}&store_id=${storeId}&item_id=${itemId}`),

  createEvent: (datasetId: number, event: { name: string; start_date: string; end_date: string; expected_demand_impact_pct: number }) =>
    request(`/api/events?dataset_id=${datasetId}`, { method: "POST", body: JSON.stringify(event) }),
  listEvents: (datasetId: number) => request(`/api/events?dataset_id=${datasetId}`),
  applyEvent: (eventId: number, datasetId: number, storeId: number, itemId: number, currentStock: number) =>
    request(`/api/events/${eventId}/apply?dataset_id=${datasetId}&store_id=${storeId}&item_id=${itemId}&current_stock=${currentStock}`, { method: "POST" }),

  getAbcXyz: (datasetId: number) => request(`/api/analytics/abc-xyz?dataset_id=${datasetId}`),
  getAlerts: (datasetId: number) => request(`/api/alerts?dataset_id=${datasetId}`),
  getAnomalies: (datasetId: number, zThreshold = 3.0) =>
    request(`/api/analytics/anomalies?dataset_id=${datasetId}&z_threshold=${zThreshold}`),
  search: (q: string) => request(`/api/search?q=${encodeURIComponent(q)}`),
  whatIf: (datasetId: number, params: Record<string, number>) => {
    const qs = new URLSearchParams({ dataset_id: String(datasetId), ...Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])) });
    return request(`/api/scenarios/what-if?${qs.toString()}`, { method: "POST" });
  },
  getScenarioPlanning: (datasetId: number, storeId: number, itemId: number, currentStock: number) =>
    request(`/api/scenarios/planning?dataset_id=${datasetId}&store_id=${storeId}&item_id=${itemId}&current_stock=${currentStock}`),
  getDemandBehavior: (datasetId: number) => request(`/api/analytics/demand-behavior?dataset_id=${datasetId}`),
  askInsights: (datasetId: number, question: string) =>
    request(`/api/insights/ask?dataset_id=${datasetId}&question=${encodeURIComponent(question)}`),

  getRegistry: () => request("/api/models/registry"),
  getMonitoring: (datasetId: number) => request(`/api/models/monitoring?dataset_id=${datasetId}`),
  updateModelStatus: (modelVersionId: number, status: string) =>
    request(`/api/models/registry/${modelVersionId}/status?status=${status}`, { method: "PATCH" }),
  compareModels: (ids: number[]) => request(`/api/models/compare?model_version_ids=${ids.join(",")}`),
  getRecommendations: (datasetId: number) => request(`/api/recommendations?dataset_id=${datasetId}`),
  getAuditLogs: () => request("/api/audit-logs"),

  downloadReport: async (path: string, filename: string) => {
    const blob: Blob = await request(path);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    window.URL.revokeObjectURL(url);
  },
};
