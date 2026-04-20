async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  let data = null;
  try {
    data = await response.json();
  } catch (_err) {
    data = null;
  }

  if (!response.ok) {
    const detail = normalizeErrorDetail(data?.detail, response.status);
    throw new Error(detail);
  }

  return data ?? {};
}

functionnormalizeErrorDetail(detail, statusCode) {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const translated = translateValidationItem(item);
          if (translated) return translated;
          if (typeof item.msg === "string") return item.msg;
          return JSON.stringify(item);
        }
        return String(item);
      })
      .join("；");
  }
  if (detail && typeof detail === "object") {
    if (typeof detail.msg === "string") {
      return detail.msg;
    }
    return JSON.stringify(detail);
  }
  return `请求失败：${statusCode}`;
}

function translateValidationItem(item) {
  if (!item || typeof item !== "object") return "";
  const fieldRaw = Array.isArray(item.loc) && item.loc.length ? item.loc[item.loc.length - 1] : "";
  const field = translateFieldName(fieldRaw);
  const ctx = item.ctx || {};

  switch (item.type) {
    case "string_too_short":
      return `${field}长度不能少于 ${ctx.min_length ?? "最小值"} 个字符`;
    case "string_too_long":
      return `${field}长度不能超过 ${ctx.max_length ?? "最大值"} 个字符`;
    case "missing":
      return `${field}为必填项`;
    case "int_parsing":
    case "float_parsing":
      return `${field}格式不正确`;
    case "greater_than_equal":
      return `${field}不能小于 ${ctx.ge ?? 0}`;
    case "less_than_equal":
      return `${field}不能大于 ${ctx.le ?? 0}`;
    case "literal_error":
      if (Array.isArray(ctx.expected)) {
        return `${field}只能为：${ctx.expected.join("、")}`;
      }
      return `${field}取值不合法`;
    default:
      if (typeof item.msg === "string" && field) {
        return `${field}：${item.msg}`;
      }
      return typeof item.msg === "string" ? item.msg : "";
  }
}

function translateFieldName(field) {
  const map = {
    name: "姓名",
    relationship: "关系",
    target_username: "目标用户名",
    ward_username: "被监护用户名",
    username: "用户名",
    password: "密码",
    current_password: "当前密码",
    new_password: "新密码",
    phone: "手机号",
    text: "文本",
    media_type: "媒体类型",
    file: "文件",
    status: "状态",
    decision: "处理动作",
  };
  return map[field] || String(field || "字段");
}

function buildAuthHeaders(token, withJson = true) {
  const headers = {};
  if (withJson) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export async function postJson(url, payload) {
  return requestJson(url, {
    method: "POST",
    headers: buildAuthHeaders(null, true),
    body: JSON.stringify(payload),
  });
}

export async function getJson(url, token) {
  return requestJson(url, {
    method: "GET",
    headers: buildAuthHeaders(token, false),
  });
}

export async function postJsonWithToken(url, payload, token) {
  return requestJson(url, {
    method: "POST",
    headers: buildAuthHeaders(token, true),
    body: JSON.stringify(payload),
  });
}

export async function postFormDataWithToken(url, formData, token) {
  return requestJson(url, {
    method: "POST",
    headers: buildAuthHeaders(token, false),
    body: formData,
  });
}

export async function putJson(url, payload, token) {
  return requestJson(url, {
    method: "PUT",
    headers: buildAuthHeaders(token, true),
    body: JSON.stringify(payload),
  });
}

export async function deleteJson(url, token) {
  return requestJson(url, {
    method: "DELETE",
    headers: buildAuthHeaders(token, false),
  });
}
