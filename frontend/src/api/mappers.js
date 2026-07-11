const riskLabelMap = {
  high: '高',
  mid_high: '中高',
  medium_high: '中高',
  mid: '中',
  medium: '中',
  low: '低',
  高: '高',
  中高: '中高',
  中: '中',
  低: '低',
};

const stageLabelMap = {
  latent: '潜伏期',
  growth: '成长期',
  peak: '高潮期',
  decline: '衰退期',
  潜伏期: '潜伏期',
  成长期: '成长期',
  高潮期: '高潮期',
  衰退期: '衰退期',
};

function toDisplayTime(value) {
  if (!value) return '';
  const text = String(value).replace('T', ' ');
  return text.length >= 16 ? text.slice(0, 16) : text;
}

function toHourLabel(value) {
  if (!value) return '';
  const text = String(value).replace('T', ' ');
  const match = text.match(/(\d{2}:\d{2})/);
  return match ? match[1] : text;
}

function toTrendLabel(value) {
  if (!value) return '';
  const text = String(value).replace('T', ' ');
  const timeMatch = text.match(/(\d{2}:\d{2})/);
  if (timeMatch) return timeMatch[1];
  const dateMatch = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return dateMatch ? `${dateMatch[2]}-${dateMatch[3]}` : text;
}

function normalizePeopleText(value) {
  if (!value) return '';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.filter(Boolean).join('、');
  if (typeof value === 'object') {
    return Object.values(value)
      .flatMap((item) => (Array.isArray(item) ? item : [item]))
      .filter((item) => typeof item === 'string' && item)
      .join('、');
  }
  return String(value);
}

function normalizeAuthenticity(raw = {}, analytics = {}) {
  const authenticity = raw.authenticity || analytics.authenticity || {};
  return authenticity && typeof authenticity === 'object' ? authenticity : {};
}

function normalizeDuplicateRate(value) {
  const normalized = normalizePercent(value);
  return `${normalized}%`;
}

function pickTrendData(raw = {}) {
  if (raw.trend_daily?.length) return raw.trend_daily;
  if (raw.trend?.length && raw.future_trend?.length) return [...raw.trend, ...raw.future_trend];
  return raw.trend || raw.future_trend || [];
}

function normalizeTrendValue(item = {}) {
  const isPredicted = Number(item.is_predicted ?? item.isPredicted ?? 0) === 1;
  if (isPredicted) return Number(item.predict_count ?? item.predict_heat ?? item.value ?? item.count ?? 0);
  return Number(item.value ?? item.count ?? item.predict_count ?? item.predict_heat ?? 0);
}

function normalizeKeywordLabels(rawKeywords = []) {
  return rawKeywords
    .map((item) => {
      if (typeof item === 'string') return item;
      if (Array.isArray(item)) return item[0];
      return item.word || item.keyword || item.name;
    })
    .filter(Boolean);
}

function normalizeKeywordWeights(rawKeywords = []) {
  return rawKeywords
    .map((item) => {
      if (Array.isArray(item)) return item;
      if (typeof item === 'string') return [item, 50];
      return [item.word || item.keyword || item.name, item.weight ?? item.value ?? 50];
    })
    .filter(([word]) => Boolean(word));
}

function normalizePercent(value) {
  const number = Number(value ?? 0);
  if (!Number.isFinite(number)) return 0;
  return number > 0 && number <= 1 ? Math.round(number * 1000) / 10 : number;
}

export function normalizeEventSummary(raw = {}) {
  const sentiment = raw.sentiment || {};
  return {
    id: String(raw.event_id ?? raw.id ?? raw.eventId ?? ''),
    title: raw.title || raw.event_title || '',
    category: raw.category || raw.field || '未分类',
    time: toDisplayTime(raw.event_time || raw.time || raw.publish_time),
    location: raw.location || raw.area || '未标注地区',
    summary: raw.summary || raw.description || raw.analysis || '',
    heat: Number(raw.heat ?? raw.heat_index ?? 0),
    risk: riskLabelMap[raw.risk_level || raw.risk] || raw.risk_level || raw.risk || '中',
    stage: stageLabelMap[raw.stage] || raw.stage || '成长期',
    reportCount: Number(raw.report_count ?? raw.reportCount ?? raw.article_count ?? 0),
    sentiment: {
      positive: normalizePercent(sentiment.positive ?? raw.positive),
      neutral: normalizePercent(sentiment.neutral ?? raw.neutral),
      negative: normalizePercent(sentiment.negative ?? raw.negative),
    },
    keywords: normalizeKeywordLabels(raw.keywords),
  };
}

export function normalizeEventDetail(raw = {}) {
  const analytics = raw.analytics || {};
  const authenticity = normalizeAuthenticity(raw, analytics);
  const traceability = analytics.traceability || {};
  const lifecycle = raw.lifecycle || {};
  const summary = normalizeEventSummary(raw);
  const platformData = raw.platforms || raw.platform_distribution || [];
  const keywordData = raw.words || raw.keywords || [];
  const trendData = pickTrendData(raw);

  return {
    ...summary,
    cause: raw.cause || raw.reason || '',
    people: normalizePeopleText(raw.people || raw.subjects),
    falseConfidence: Number(raw.falseConfidence ?? raw.false_confidence ?? raw.confidence ?? authenticity.false_confidence ?? authenticity.falseConfidence ?? 0.85),
    duplicateRate: raw.duplicateRate || raw.duplicate_rate || normalizeDuplicateRate(authenticity.duplicate_rate ?? authenticity.duplicateRate ?? 0),
    platforms: platformData.map((item) => ({
      name: item.name || item.platform_name || item.platform || '',
      value: normalizePercent(item.value ?? item.ratio),
    })),
    trend: trendData.map((item) => ({
      time: toTrendLabel(item.time || item.date),
      value: normalizeTrendValue(item),
      predicted: Number(item.is_predicted ?? item.isPredicted ?? 0) === 1,
      node: item.node,
    })),
    words: normalizeKeywordWeights(keywordData),
    similarEvents: (analytics.similar_events || raw.similarEvents || raw.similar_events || []).map((item) =>
      typeof item === 'string' ? item : item.title,
    ),
    pathNodes: (raw.pathNodes || raw.path_nodes || traceability.nodes || []).map((item) => ({
      name: item.name,
      category: Number(item.category ?? 0),
      symbolSize: Number(item.symbolSize ?? item.symbol_size ?? 42),
    })),
    pathLinks: (raw.pathLinks || raw.path_links || traceability.links || []).map((item) => {
      if (Array.isArray(item)) return item;
      return [item.source, item.target];
    }),
    qaSeed: raw.qaSeed || raw.qa_seed || '',
    advice: raw.advice || raw.suggestion || '',
    geoDiscussion: (analytics.geo_discussion || raw.geoDiscussion || raw.geo_discussion || []).map((item) => ({
      name: item.name,
      displayName: item.displayName || item.display_name,
      lng: Number(item.lng),
      lat: Number(item.lat),
      value: Number(item.value ?? 0),
    })),
    authenticity,
    lifecycle: {
      ...lifecycle,
      stage: stageLabelMap[lifecycle.stage] || lifecycle.stage,
    },
    analytics,
  };
}

export function normalizePlatformSetting(raw = {}) {
  return {
    name: raw.name || raw.platform_name || '新采集源',
    url: raw.url || 'https://',
    frequency: raw.frequency || (raw.frequency_minutes ? `${raw.frequency_minutes} 分钟` : '10 分钟'),
    status: raw.status === 'limited' ? '限流' : raw.status === 'error' ? '限流' : raw.status || '正常',
  };
}
