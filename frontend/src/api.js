// 所有解析、编号、校验、渲染都通过这里调用后端；前端不自行计算编号。
const BASE = "/api";

async function post(path, body) {
  const resp = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    const err = new Error(
      typeof detail.detail === "string"
        ? detail.detail
        : detail.detail?.message || `请求失败 ${resp.status}`,
    );
    err.status = resp.status;
    err.detail = detail.detail;
    throw err;
  }
  return resp.json();
}

async function get(path) {
  const resp = await fetch(BASE + path);
  if (!resp.ok) throw new Error(`请求失败 ${resp.status}`);
  return resp.json();
}

// 一次分析：编号重排 + 交叉引用 + 结构错误 + 后端 SVG 渲染
export function analyze(formulas, { base = 1, tolerant = true, fontsize = 18 } = {}) {
  return post("/analyze", { formulas, base, tolerant, fontsize });
}

// 单段解析：token（高亮用）与结构错误
export function parseSource(source) {
  return post("/parse", { source });
}

export const workspacesApi = {
  list: () => get("/workspaces").then((d) => d.workspaces),
  get: (id) => get(`/workspaces/${id}`),
  create: (payload) => post("/workspaces", payload),
  save: (id, payload) =>
    fetch(`${BASE}/workspaces/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(async (resp) => {
      if (resp.status === 409) {
        const d = await resp.json();
        const err = new Error(d.detail?.message || "工作区已被其他会话修改");
        err.status = 409;
        err.detail = d.detail;
        throw err;
      }
      if (!resp.ok) throw new Error(`保存失败 ${resp.status}`);
      return resp.json();
    }),
  remove: (id) =>
    fetch(`${BASE}/workspaces/${id}`, { method: "DELETE" }).then((r) => r.json()),
};
