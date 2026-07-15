const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function pad(value) {
  return String(value).padStart(2, '0');
}

export function buildTimestamp(date = new Date()) {
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
    '-',
    pad(date.getHours()),
    pad(date.getMinutes()),
    pad(date.getSeconds()),
  ].join('');
}

export function sanitizeFilePart(value, fallback = '未命名') {
  const text = String(value || fallback)
    .replace(/[\\/:*?"<>|#\[\]{}]/g, '')
    .replace(/\s+/g, '')
    .trim();
  return text || fallback;
}

export function toQuery(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value);
  });
  const text = query.toString();
  return text ? `?${text}` : '';
}

export async function downloadPdfFromBackend(path, filename) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `PDF 导出失败，状态码 ${response.status}`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function postPdfToBackend(path, body, filename) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `PDF 导出失败，状态码 ${response.status}`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
