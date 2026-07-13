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
  const authenticity = raw.authenticity ?? analytics.authenticity ?? {};
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

export function normalizeSimilarEvents(rawSimilarEvents = []) {
  return rawSimilarEvents
    .map((item, index) => {
      if (typeof item === 'string') {
        return {
          id: item,
          title: item,
          similarity: null,
          reason: '',
        };
      }
      if (!item || typeof item !== 'object') return null;
      const title = item.title || item.event_title || item.name || '';
      if (!title) return null;
      const rawSimilarity = Number(item.similarity ?? item.score ?? item.similarity_score);
      return {
        id: String(item.event_id ?? item.id ?? `${title}-${index}`),
        title,
        similarity: Number.isFinite(rawSimilarity) ? rawSimilarity : null,
        reason: item.reason || item.match_reason || item.description || '',
      };
    })
    .filter(Boolean);
}

export function normalizeAdvice(rawAdvice) {
  if (!rawAdvice) {
    return {
      summary: '还没有处置建议。',
      items: [],
    };
  }

  if (typeof rawAdvice === 'string') {
    return {
      summary: rawAdvice,
      items: [],
    };
  }

  if (typeof rawAdvice !== 'object') {
    return {
      summary: String(rawAdvice),
      items: [],
    };
  }

  const items = [
    ['风险判断', rawAdvice.risk_assessment ?? rawAdvice.riskAssessment],
    ['信息核验', rawAdvice.verification],
    ['处置建议', rawAdvice.response_strategy ?? rawAdvice.responseStrategy],
  ]
    .map(([label, text]) => ({ label, text: String(text || '').trim() }))
    .filter((item) => item.text);

  return {
    summary: items.length ? items.map((item) => `${item.label}：${item.text}`).join(' ') : '还没有处置建议。',
    items,
  };
}

function normalizePropagationRole(node = {}, index = 0) {
  const role = String(node.role || '').trim();
  const verificationType = String(node.verification_type || node.verificationType || '').trim();

  if (/初始|首发|爆料/.test(role)) return 0;
  if (/高峰|峰值/.test(role)) return 3;
  if (/大V|意见领袖/.test(role) || /头部认证个人|认证机构/.test(verificationType)) return 1;
  if (/官方|媒体|通报/.test(role) || /官方平台|官方机构/.test(verificationType)) return 2;
  return index === 0 ? 0 : 4;
}

function normalizePropagationNodeName(node = {}, index = 0) {
  const role = String(node.role || `传播节点${index + 1}`).trim();
  const author = String(node.author || '').trim();
  const platform = String(node.platform || '').trim();
  const subject = author && author !== '匿名' ? author : platform;
  return subject ? `${role} · ${subject}` : role;
}

function normalizePropagationSymbolSize(node = {}, index = 0) {
  const influence = Number(node.influence ?? 0);
  if (!Number.isFinite(influence) || influence <= 0) return Math.max(34, 48 - index * 2);
  return Math.min(72, Math.max(38, 34 + Math.sqrt(influence)));
}

function normalizePropagationPath(rawPropagation = {}) {
  const propagation = rawPropagation && typeof rawPropagation === 'object' ? rawPropagation : {};
  const rawKeyNodes = propagation.key_nodes || propagation.keyNodes || [];
  const keyNodes = rawKeyNodes
    .map((node, index) => {
      if (!node || typeof node !== 'object') return null;
      return {
        ...node,
        name: normalizePropagationNodeName(node, index),
        category: normalizePropagationRole(node, index),
        symbolSize: normalizePropagationSymbolSize(node, index),
      };
    })
    .filter(Boolean);

  const platformChain = propagation.platform_chain || propagation.platformChain || {};
  const platformNodes = (platformChain.nodes || [])
    .map((node, index) => {
      if (!node || typeof node !== 'object') return null;
      const count = Number(node.count ?? 0);
      return {
        ...node,
        name: String(node.name || `平台${index + 1}`),
        category: index === 0 ? 0 : 3,
        symbolSize: Math.min(66, Math.max(34, 34 + Math.sqrt(Number.isFinite(count) ? count : 0) * 2)),
      };
    })
    .filter(Boolean);

  const pathNodes = keyNodes.length ? keyNodes : platformNodes;
  const pathLinks = keyNodes.length
    ? keyNodes.slice(1).map((node, index) => [keyNodes[index].name, node.name])
    : (platformChain.links || []).map((item) => {
        if (Array.isArray(item)) return item;
        return [item.source, item.target];
      });

  const topInfluencers = (propagation.top_influencers || propagation.topInfluencers || [])
    .map((item, index) => {
      if (!item || typeof item !== 'object') return null;
      return {
        id: String(item.author || item.title || index),
        author: item.author || '匿名',
        platform: item.platform || '',
        verificationType: item.verification_type || item.verificationType || '普通用户',
        publishTime: toDisplayTime(item.publish_time || item.publishTime),
        influence: Number(item.influence ?? 0),
        title: item.title || '',
      };
    })
    .filter(Boolean);

  return {
    keyNodes,
    topInfluencers,
    platformChain,
    pathNodes,
    pathLinks,
  };
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
  const advice = normalizeAdvice(raw.advice || raw.suggestion);
  const propagation = normalizePropagationPath(raw.propagation || analytics.propagation || {});
  const explicitPathNodes = raw.pathNodes || raw.path_nodes || traceability.nodes || [];
  const explicitPathLinks = raw.pathLinks || raw.path_links || traceability.links || [];

  return {
    ...summary,
    cause: raw.cause || raw.reason || '',
    people: normalizePeopleText(raw.people || raw.subjects),
    falseConfidence: Number(
      raw.falseConfidence
        ?? raw.false_confidence
        ?? authenticity.credibility_score
        ?? authenticity.credibilityScore
        ?? raw.confidence
        ?? authenticity.false_confidence
        ?? authenticity.falseConfidence
        ?? 0.85,
    ),
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
    similarEvents: normalizeSimilarEvents(analytics.similar_events || raw.similarEvents || raw.similar_events || []),
    propagation: {
      ...(raw.propagation || analytics.propagation || {}),
      keyNodes: propagation.keyNodes,
      topInfluencers: propagation.topInfluencers,
      platformChain: propagation.platformChain,
    },
    pathNodes: (explicitPathNodes.length ? explicitPathNodes : propagation.pathNodes).map((item) => ({
      ...item,
      name: item.name,
      category: Number(item.category ?? 0),
      symbolSize: Number(item.symbolSize ?? item.symbol_size ?? 42),
    })),
    pathLinks: (explicitPathLinks.length ? explicitPathLinks : propagation.pathLinks).map((item) => {
      if (Array.isArray(item)) return item;
      return [item.source, item.target];
    }),
    qaSeed: raw.qaSeed || raw.qa_seed || '',
    advice: advice.summary,
    adviceItems: advice.items,
    geoDiscussion: (analytics.geo_discussion || raw.geoDiscussion || raw.geo_discussion || []).map((item) => ({
      name: item.name,
      displayName: item.displayName || item.display_name,
      lng: Number(item.lng),
      lat: Number(item.lat),
      value: Number(item.value ?? 0),
    })),
    authenticity,
    authenticityLevel: raw.authenticity_level || raw.authenticityLevel || authenticity.level || '',
    authenticityLabel: raw.authenticity_label || raw.authenticityLabel || authenticity.label || '',
    authenticityDescription: raw.authenticity_description || raw.authenticityDescription || authenticity.description || '',
    lifecycle: {
      ...lifecycle,
      stage: stageLabelMap[lifecycle.stage] || lifecycle.stage,
    },
    analytics,
  };
}

export function normalizePlatformSetting(raw = {}) {
  return {
    name: raw.name || raw.platform_name || '新监测源',
    url: raw.url || 'https://',
    frequency: raw.frequency || (raw.frequency_minutes ? `${raw.frequency_minutes} 分钟` : '10 分钟'),
    status: raw.status === 'limited' ? '限流' : raw.status === 'error' ? '限流' : raw.status || '正常',
  };
}
