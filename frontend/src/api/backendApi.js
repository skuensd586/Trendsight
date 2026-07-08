import { normalizeEventDetail, normalizeEventSummary } from './mappers.js';

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
  const payload = await response.json();
  if (!response.ok || payload.code !== 200) {
    throw new Error(payload.message || `Request failed: ${response.status}`);
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

async function optionalRequest(path) {
  try {
    return await request(path);
  } catch (_error) {
    return null;
  }
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
    const data = await request(`/api/events/hot${toQuery(params)}`);
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
    const [base, trend, sentiment, platform, keywords, lifecycle] = await Promise.all([
      request(`/api/events/${eventId}`),
      optionalRequest(`/api/events/${eventId}/trend`),
      optionalRequest(`/api/events/${eventId}/sentiment`),
      optionalRequest(`/api/events/${eventId}/platform`),
      optionalRequest(`/api/events/${eventId}/keywords`),
      optionalRequest(`/api/events/${eventId}/lifecycle`),
    ]);

    return normalizeEventDetail({
      ...base,
      trend: trend?.trend || base.trend,
      sentiment: sentiment || base.sentiment,
      platform_distribution: platform?.platform_distribution || base.platform_distribution,
      keywords: keywords?.keywords || base.keywords,
      lifecycle,
    });
  },

  async askEventQuestion({ eventId, conversationId, question }) {
    return request(`/api/events/${eventId}/qa`, {
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
