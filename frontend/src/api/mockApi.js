import { events, focusAreas, focusKeywords, platformSettings } from '../data/events.js';

function sortEvents(items, sort = 'heat') {
  return [...items].sort((first, second) => {
    if (sort === 'time') return new Date(second.time.replace(' ', 'T')) - new Date(first.time.replace(' ', 'T'));
    if (sort === 'negative') return second.sentiment.negative - first.sentiment.negative;
    return second.heat - first.heat;
  });
}

function filterEvents({ q = '', risk_level = 'all', time_range = '7d', sort = 'heat', page = 1, page_size = 50 } = {}) {
  const normalizedQuery = q.trim();
  const filtered = events
    .filter((event) => {
      if (!normalizedQuery) return true;
      return [event.title, event.category, event.location, ...event.keywords].some((text) => text.includes(normalizedQuery));
    })
    .filter((event) => {
      if (risk_level === 'all') return true;
      if (risk_level === 'high') return ['高', '中高'].includes(event.risk);
      if (risk_level === 'mid_high') return event.risk === '中高';
      if (risk_level === 'mid') return event.risk === '中';
      return event.risk === '低';
    })
    .filter((event) => {
      if (time_range === 'today') return event.time.startsWith('2026-07-07');
      return true;
    });
  const sorted = sortEvents(filtered, sort);
  const start = (Number(page) - 1) * Number(page_size);
  const items = sorted.slice(start, start + Number(page_size));
  return {
    items,
    pagination: {
      page: Number(page),
      page_size: Number(page_size),
      total: sorted.length,
      total_pages: Math.max(1, Math.ceil(sorted.length / Number(page_size))),
    },
  };
}

export const mockApi = {
  async login({ username }) {
    return {
      user_id: 1,
      username,
      token: 'mock-token',
    };
  },

  async getUserProfile() {
    return {
      user_id: 1,
      username: localStorage.getItem('trendsight-user') || 'analyst',
      preferences: {
        fields: focusAreas,
        keywords: focusKeywords,
        platform_urls: platformSettings.map((source) => ({
          platform_name: source.name,
          url: source.url,
          frequency: source.frequency,
          status: source.status,
        })),
      },
    };
  },

  async updateUserPreferences(preferences) {
    return preferences;
  },

  async getHotEvents(params) {
    return filterEvents(params);
  },

  async getEventDetail(eventId) {
    return events.find((event) => event.id === String(eventId)) || events[0];
  },

  async askEventQuestion({ eventId, question }) {
    const event = events.find((item) => item.id === String(eventId)) || events[0];
    return {
      conversation_id: `mock-${event.id}`,
      answer: event.qaSeed || `已收到问题：${question}`,
      created_time: new Date().toISOString(),
    };
  },

  async getConversationHistory() {
    return {
      conversation_id: 'mock',
      messages: [],
    };
  },
};
