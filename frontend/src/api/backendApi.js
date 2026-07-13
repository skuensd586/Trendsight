import { normalizeAdvice, normalizeEventDetail, normalizeEventSummary, normalizeSimilarEvents } from './mappers.js';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function authHeaders() {
  const token = localStorage.getItem('trendsight-token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...options.headers,
    },
  });
  const rawPayload = await response.text();
  let payload = {};
  if (rawPayload) {
    try {
      payload = JSON.parse(rawPayload);
    } catch (_error) {
      payload = { detail: rawPayload };
    }
  }
  if (!response.ok || payload.code !== 200) {
    const detail = Array.isArray(payload.detail)
      ? payload.detail.map((item) => item.msg || JSON.stringify(item)).join('; ')
      : payload.detail;
    throw new Error(payload.message || detail || `请求失败，状态码 ${response.status}`);
  }
  return payload.data;
}

function toQuery(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value);
  });
  const text = query.toString();
  return text ? `?${text}` : '';
}

function toBackendEventId(eventId) {
  const numeric = Number(eventId);
  if (Number.isInteger(numeric) && numeric > 0) return String(numeric);

  return '0';
}

export const backendApi = {
  async login(body) {
    return request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  async getUserProfile() {
    return request('/api/user/profile');
  },

  async updateUserPreferences(body) {
    return request('/api/user/preferences', {
      method: 'PUT',
      body: JSON.stringify(body),
    });
  },

  async getHotEvents(params) {
    const queryParams = {
      ...params,
      size: params?.page_size ?? params?.size,
    };
    delete queryParams.page_size;
    const data = await request(`/api/events/hot${toQuery(queryParams)}`);
    return {
      items: (data.items || data.events || []).map(normalizeEventSummary),
      pagination: data.pagination || {
        page: Number(params?.page || 1),
        page_size: Number(params?.page_size || data.items?.length || 0),
        total: data.items?.length || 0,
        total_pages: 1,
      },
    };
  },

  async getEventDetail(eventId) {
    const backendEventId = toBackendEventId(eventId);
    const base = await request(`/api/events/${backendEventId}`);
    return normalizeEventDetail(base);
  },

  async getEventSimilarEvents(eventId) {
    const backendEventId = toBackendEventId(eventId);
    const data = await request(`/api/events/${backendEventId}/similar`);
    return normalizeSimilarEvents(data.similar_events || data.items || []);
  },

  async getEventAdvice(eventId) {
    const backendEventId = toBackendEventId(eventId);
    const data = await request(`/api/events/${backendEventId}/advice`);
    const advice = normalizeAdvice(data.advice || data.suggestion);
    return {
      advice: advice.summary,
      adviceItems: advice.items,
    };
  },

  async askEventQuestion({ eventId, conversationId, question }) {
    return request(`/api/events/${toBackendEventId(eventId)}/qa`, {
      method: 'POST',
      body: JSON.stringify({
        conversation_id: conversationId || '',
        question,
      }),
    });
  },

  async getConversationHistory(conversationId) {
    return request(`/api/qa/history/${conversationId}`);
  },
};
