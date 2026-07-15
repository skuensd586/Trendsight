import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Download, FileCheck2, Flame, Loader2, Network, ShieldCheck } from 'lucide-react';
import AppShell from '../components/AppShell.jsx';
import EChart from '../components/EChart.jsx';
import QAPanel from '../components/QAPanel.jsx';
import SentimentBar from '../components/SentimentBar.jsx';
import WordCloud from '../components/WordCloud.jsx';
import { api, isBackendMode } from '../api/index.js';
import { events } from '../data/events.js';
import { clusterPoints } from '../data/mockAnalytics.js';
import { buildTimestamp, postPdfToBackend, sanitizeFilePart } from '../utils/briefExport.js';

const chartColors = ['#469B78', '#4E74BD', '#C93F45', '#D4783A', '#7962B3'];
const stageClass = {
  高潮期: 'stage-peak',
  成长期: 'stage-growth',
  衰退期: 'stage-decline',
  潜伏期: 'stage-latent',
};
const riskClass = {
  高: 'risk-high',
  中高: 'risk-mid-high',
  中: 'risk-mid',
  低: 'risk-low',
};
const hiddenCategoryLabels = new Set(['未分类']);
const hiddenLocationLabels = new Set(['未标注地区', '未对应地区']);
const emptyTrend = [
  { time: '00:00', value: 0 },
  { time: '04:00', value: 0 },
  { time: '08:00', value: 0 },
  { time: '12:00', value: 0 },
  { time: '16:00', value: 0 },
  { time: '20:00', value: 0 },
];
const emptyWords = [['暂无关键词', 1]];
const emptyPlatforms = [{ name: '暂无数据', value: 0 }];
const trendContextBeforeChange = 1;
const trendMinVisiblePoints = 6;
const trendMinCollapsedPoints = 2;
const trendBaselineBandRatio = 0.06;
const trendJumpBandRatio = 0.08;

function createEmptyDetailEvent(id = '') {
  return {
    id: String(id || ''),
    title: '正在加载事件详情',
    category: '未分类',
    time: '',
    location: '未标注地区',
    cause: '暂无详情数据',
    people: '暂无主体信息',
    summary: '正在加载事件详情。',
    heat: 0,
    risk: '中',
    stage: '成长期',
    falseConfidence: 0,
    duplicateRate: '0%',
    reportCount: 0,
    sentiment: { positive: 0, neutral: 100, negative: 0 },
    platforms: emptyPlatforms,
    trend: emptyTrend,
    words: emptyWords,
    keywords: ['暂无关键词'],
    similarEvents: [],
    pathNodes: [{ name: '暂无传播节点', category: 3, symbolSize: 34 }],
    pathLinks: [],
    qaSeed: '',
    advice: '还没有处置建议。',
    adviceItems: [],
    authenticityLevel: '',
    authenticityLabel: '',
    authenticityDescription: '',
    geoDiscussion: [],
  };
}

function resolveFallbackEvent(id) {
  const mockEvent = events.find((item) => item.id === id);
  if (!isBackendMode()) return mockEvent || events[0];
  return mockEvent || createEmptyDetailEvent(id);
}

function formatCount(value) {
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`;
  return value.toLocaleString();
}

function normalizeDisplayText(value) {
  return String(value || '').trim();
}

function getVisibleEventCategory(category) {
  const text = normalizeDisplayText(category);
  return text && !hiddenCategoryLabels.has(text) ? text : '';
}

function getVisibleEventLocation(location) {
  const text = normalizeDisplayText(location);
  return text && !hiddenLocationLabels.has(text) ? text : '';
}

function getEventContextTag(event) {
  return [getVisibleEventCategory(event.category), getVisibleEventLocation(event.location)].filter(Boolean).join(' · ');
}

function normalizeSimilarEventItem(item, index) {
  if (typeof item === 'string') {
    return {
      key: item,
      title: item,
      similarityLabel: '',
      reason: '',
    };
  }

  const similarity = Number(item?.similarity);
  const similarityLabel = Number.isFinite(similarity)
    ? `相似度 ${Math.round((similarity <= 1 ? similarity * 100 : similarity) * 10) / 10}%`
    : '';

  return {
    key: String(item?.id || item?.event_id || item?.title || index),
    title: item?.title || '未命名事件',
    similarityLabel,
    reason: item?.reason || '',
  };
}

function buildBaseEvent(fallbackEvent, nextEvent = {}) {
  return {
    ...fallbackEvent,
    ...nextEvent,
    sentiment: nextEvent.sentiment || fallbackEvent.sentiment,
    platforms: nextEvent.platforms?.length ? nextEvent.platforms : fallbackEvent.platforms,
    trend: nextEvent.trend?.length ? nextEvent.trend : fallbackEvent.trend,
    words: nextEvent.words?.length ? nextEvent.words : fallbackEvent.words,
    keywords: nextEvent.keywords?.length ? nextEvent.keywords : fallbackEvent.keywords,
    pathNodes: nextEvent.pathNodes?.length ? nextEvent.pathNodes : fallbackEvent.pathNodes,
    pathLinks: nextEvent.pathLinks?.length ? nextEvent.pathLinks : fallbackEvent.pathLinks,
    similarEvents: [],
    advice: '',
    adviceItems: [],
  };
}

function getInitialDeferredContent(event, keepFallbackContent) {
  return {
    similarEvents: keepFallbackContent ? event.similarEvents || [] : [],
    advice: keepFallbackContent ? event.advice || '' : '',
    adviceItems: keepFallbackContent ? event.adviceItems || [] : [],
  };
}

function getTrendValue(item) {
  const value = Number(item?.value ?? 0);
  return Number.isFinite(value) ? value : 0;
}

function normalizeTrendSeries(trend) {
  const sourceTrend = trend?.length ? trend : emptyTrend;
  return sourceTrend.map((item, index) => ({
    ...(item || {}),
    time: item?.time || String(index + 1),
    value: getTrendValue(item),
  }));
}

function findFirstMeaningfulTrendIndex(trend) {
  const values = trend.map((item) => item.value);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min;

  if (range <= 0) return 0;

  const baseline = values[0];
  const valueReference = Math.max(Math.abs(max), Math.abs(baseline), 1);
  const baselineBand = Math.max(range * trendBaselineBandRatio, valueReference * 0.01, 1);
  const jumpBand = Math.max(range * trendJumpBandRatio, valueReference * 0.015, 1);

  for (let index = 1; index < values.length; index += 1) {
    const baselineMove = Math.abs(values[index] - baseline);
    const localJump = Math.abs(values[index] - values[index - 1]);

    if (baselineMove >= baselineBand || localJump >= jumpBand) {
      return index;
    }
  }

  return 0;
}

function buildVisibleTrend(trend) {
  const normalizedTrend = normalizeTrendSeries(trend);
  const firstMeaningfulIndex = findFirstMeaningfulTrendIndex(normalizedTrend);

  if (!firstMeaningfulIndex) return normalizedTrend;

  const minVisibleCount = Math.min(trendMinVisiblePoints, normalizedTrend.length);
  let startIndex = Math.max(0, firstMeaningfulIndex - trendContextBeforeChange);

  if (normalizedTrend.length - startIndex < minVisibleCount) {
    startIndex = Math.max(0, normalizedTrend.length - minVisibleCount);
  }

  if (startIndex < trendMinCollapsedPoints) return normalizedTrend;

  return normalizedTrend.slice(startIndex);
}

function buildTrendOption(visibleTrend) {
  const trend = normalizeTrendSeries(visibleTrend);
  const trendData = trend.map((item) => item.value);
  const peak = trend.reduce((current, item) => (item.value > current.value ? item : current), trend[0]);
  const peakIndex = trend.findIndex((item) => item === peak);
  const peakAreaStart = trend[Math.max(0, peakIndex - 1)]?.time || peak.time;
  const peakAreaEnd = trend[Math.min(trend.length - 1, peakIndex + 1)]?.time || peak.time;
  const keyNodes = trend
    .filter((item) => item.node)
    .map((item) => ({
      name: item.node,
      value: [item.time, item.value],
    }));

  return {
    color: ['#D7E3F8', '#366FB8'],
    tooltip: { trigger: 'axis' },
    legend: {
      top: 0,
      right: 12,
      icon: 'roundRect',
      textStyle: { color: '#444A56' },
    },
    grid: { top: 44, right: 28, left: 58, bottom: 36 },
    xAxis: {
      type: 'category',
      boundaryGap: true,
      data: trend.map((item) => item.time),
      axisLine: { lineStyle: { color: '#E2E7EF' } },
      axisLabel: { color: '#868F9E' },
    },
    yAxis: {
      type: 'value',
      name: '报道量（条）',
      nameTextStyle: { color: '#868F9E', align: 'right' },
      splitLine: { lineStyle: { color: '#E8EEF3' } },
      axisLabel: { color: '#868F9E' },
    },
    series: [
      {
        name: '报道量',
        type: 'bar',
        barWidth: 28,
        itemStyle: {
          color: '#D7E3F8',
          borderRadius: [6, 6, 0, 0],
        },
        data: trendData,
      },
      {
        name: '趋势',
        type: 'line',
        smooth: 0.25,
        symbolSize: 8,
        lineStyle: { width: 4, color: '#366FB8' },
        itemStyle: { color: '#366FB8' },
        data: trendData,
        markArea: {
          itemStyle: { color: 'rgba(54, 111, 184, 0.08)' },
          data: trend.length > 1 ? [[{ xAxis: peakAreaStart }, { xAxis: peakAreaEnd }]] : [],
        },
        markPoint: {
          symbol: 'circle',
          symbolSize: 12,
          label: {
            formatter: `峰值 ${peak.value.toLocaleString()}`,
            position: 'top',
            distance: 12,
            color: '#D4783A',
            fontWeight: 800,
            backgroundColor: '#fff',
            borderColor: 'rgba(212, 120, 58, 0.26)',
            borderWidth: 1,
            borderRadius: 4,
            padding: [4, 8],
          },
          data: [{ coord: [peak.time, peak.value], value: peak.value, itemStyle: { color: '#D4783A' } }],
        },
        markLine: {
          symbol: 'none',
          lineStyle: { color: '#D4783A', type: 'dashed', width: 1.4 },
          label: {
            formatter: `峰值 ${peak.value.toLocaleString()}`,
            color: '#D4783A',
            fontWeight: 700,
          },
          data: [{ yAxis: peak.value }],
        },
      },
      {
        name: '事件点',
        type: 'scatter',
        symbolSize: 9,
        itemStyle: {
          color: '#D4783A',
          borderColor: '#fff',
          borderWidth: 2,
        },
        tooltip: {
          formatter: (params) => `${params.name}<br/>${params.value[0]}：${params.value[1].toLocaleString()} 条`,
        },
        data: keyNodes,
      },
    ],
  };
}

function buildPieOption(event) {
  const sentimentData = [
    { name: '正向', value: event.sentiment.positive },
    { name: '中性', value: event.sentiment.neutral },
    { name: '负向', value: event.sentiment.negative },
  ];
  const dominant = sentimentData.reduce((current, item) => (item.value > current.value ? item : current), sentimentData[0]);
  const conclusion = dominant.name === '正向' ? '正向为主' : dominant.name === '负向' ? '负向偏高' : '中性为主';

  return {
    color: chartColors,
    tooltip: { trigger: 'item' },
    title: {
      text: conclusion,
      subtext: `${dominant.name} ${dominant.value}%`,
      left: 'center',
      top: '36%',
      textStyle: {
        color: '#1A1F27',
        fontSize: 16,
        fontWeight: 850,
      },
      subtextStyle: {
        color: dominant.name === '正向' ? '#469B78' : dominant.name === '负向' ? '#C93F45' : '#4E74BD',
        fontSize: 20,
        fontWeight: 900,
      },
    },
    legend: { show: false },
    series: [
      {
        name: '情绪分布',
        type: 'pie',
        radius: ['56%', '74%'],
        center: ['50%', '46%'],
        padAngle: 3,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#fff',
          borderWidth: 3,
        },
        label: {
          formatter: '{b} {d}%',
          color: '#1A1F27',
          fontWeight: 760,
        },
        labelLine: {
          length: 10,
          length2: 8,
        },
        data: sentimentData,
      },
    ],
  };
}

function getKeywordCategory(word) {
  if (['救援', '物资', '转移', '求助', '补偿', '改签'].includes(word)) return 0;
  if (['暴雨', '积水', '路况', '延误', '高温', '停水'].includes(word)) return 1;
  if (['应急', '通报', '气象预警', '公告', '说明', '规则'].includes(word)) return 2;
  return 3;
}

const keywordCategoryMeta = [
  { name: '救援行动', color: '#469B78', words: ['救援', '物资', '转移', '求助', '补偿', '改签'] },
  { name: '灾害影响', color: '#D4783A', words: ['暴雨', '积水', '路况', '延误', '高温', '停水'] },
  { name: '官方响应', color: '#4E74BD', words: ['应急', '通报', '气象预警', '公告', '说明', '规则'] },
  { name: '公众反馈', color: '#7962B3', words: [] },
];
const keywordBlueGreenPalette = ['#2A3F54', '#366FB8', '#3A9477', '#4D8A91', '#72A7B5', '#89BDB7'];

function getKeywordCategoryMeta(word) {
  return keywordCategoryMeta.find((item) => item.words.includes(word)) || keywordCategoryMeta[keywordCategoryMeta.length - 1];
}

function getKeywordColor(_word, _value, index = 0) {
  return keywordBlueGreenPalette[index % keywordBlueGreenPalette.length];
}

function buildKeywordGroups(words) {
  return keywordCategoryMeta
    .map((category) => {
      const matched = words
        .filter(([word]) => (category.words.length ? category.words.includes(word) : !keywordCategoryMeta.some((item) => item.words.includes(word))))
        .map(([word]) => word);
      return { ...category, matched };
    })
    .filter((category) => category.matched.length);
}

function buildKeywordGraphOption(event) {
  const categories = [
    { name: '行动救援类', itemStyle: { color: '#469B78' } },
    { name: '灾害影响类', itemStyle: { color: '#D4783A' } },
    { name: '官方响应类', itemStyle: { color: '#4E74BD' } },
    { name: '公众反馈类', itemStyle: { color: '#7962B3' } },
  ];
  const nodes = event.words.map(([word, weight]) => ({
    name: word,
    value: weight,
    category: getKeywordCategory(word),
    symbolSize: 18 + weight / 2.8,
    label: { fontSize: weight > 70 ? 15 : 12 },
  }));
  const coreWords = nodes.slice(0, 3).map((node) => node.name);
  const links = nodes.flatMap((node, index) => {
    if (index === 0) return [];
    const core = coreWords[index % coreWords.length];
    const sameCategory = nodes.find((item, itemIndex) => itemIndex < index && item.category === node.category);
    return [
      { source: core, target: node.name, value: Math.max(1, Math.round(node.value / 18)) },
      sameCategory ? { source: sameCategory.name, target: node.name, value: Math.max(1, Math.round(node.value / 24)) } : null,
    ].filter(Boolean);
  });

  return {
    tooltip: {
      formatter: (params) => {
        if (params.dataType === 'edge') return `关联强度：${params.data.value}`;
        return `${params.name}<br/>关键词权重：${params.value}`;
      },
    },
    legend: {
      bottom: 0,
      icon: 'circle',
      textStyle: { color: '#444A56' },
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        categories,
        data: nodes,
        links,
        roam: false,
        draggable: true,
        force: {
          repulsion: 170,
          edgeLength: [44, 92],
          gravity: 0.08,
        },
        label: {
          show: true,
          color: '#1A1F27',
          fontWeight: 850,
        },
        lineStyle: {
          color: 'source',
          opacity: 0.34,
          width: 1.4,
          curveness: 0.12,
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 3 },
        },
      },
    ],
  };
}

function buildKeywordTreemapOption(event) {
  const groups = [
    { name: '行动救援类', color: '#469B78', words: ['救援', '物资', '转移', '求助', '补偿', '改签'] },
    { name: '灾害影响类', color: '#D4783A', words: ['暴雨', '积水', '路况', '延误', '高温', '停水'] },
    { name: '官方响应类', color: '#4E74BD', words: ['应急', '通报', '气象预警', '公告', '说明', '规则'] },
    { name: '公众反馈类', color: '#7962B3', words: [] },
  ];
  const childrenByGroup = groups.map((group) => ({
    name: group.name,
    itemStyle: { color: group.color },
    children: event.words
      .filter(([word]) => (group.words.length ? group.words.includes(word) : !groups.some((item) => item.words.includes(word))))
      .map(([word, weight]) => ({ name: word, value: weight })),
  }));

  return {
    tooltip: { formatter: (params) => `${params.name}<br/>关键词权重：${params.value || ''}` },
    series: [
      {
        type: 'treemap',
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        top: 8,
        right: 6,
        bottom: 8,
        left: 6,
        label: {
          color: '#1A1F27',
          fontWeight: 850,
          formatter: '{b}',
        },
        upperLabel: {
          show: true,
          height: 26,
          color: '#fff',
          fontWeight: 850,
        },
        itemStyle: {
          borderColor: '#fff',
          borderWidth: 4,
          gapWidth: 4,
          borderRadius: 8,
        },
        levels: [
          { itemStyle: { borderColor: '#fff', borderWidth: 4, gapWidth: 5 } },
          { itemStyle: { borderColor: '#fff', borderWidth: 3, gapWidth: 3 } },
        ],
        data: childrenByGroup.filter((group) => group.children.length),
      },
    ],
  };
}

function buildPlatformBarOption(event) {
  const platformData = [...event.platforms].sort((first, second) => first.value - second.value);

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: '{b}<br/>报道占比：{c}%' },
    grid: { top: 20, right: 56, bottom: 18, left: 92 },
    xAxis: {
      type: 'value',
      max: 50,
      axisLabel: { formatter: '{value}%', color: '#868F9E' },
      splitLine: { lineStyle: { color: '#E8EEF3' } },
    },
    yAxis: {
      type: 'category',
      data: platformData.map((item) => item.name),
      axisLabel: { color: '#444A56', fontWeight: 760 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'bar',
        data: platformData.map((item) => item.value),
        barWidth: 18,
        label: { show: true, position: 'right', formatter: '{c}%', color: '#444A56', fontWeight: 850 },
        itemStyle: {
          borderRadius: [0, 8, 8, 0],
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 1,
            y2: 0,
            colorStops: [
              { offset: 0, color: '#CDE5DF' },
              { offset: 1, color: '#2A3F54' },
            ],
          },
        },
      },
    ],
  };
}

function addHoursToTime(time, hours) {
  const [hour = 0, minute = 0] = time.split(':').map(Number);
  const nextHour = (hour + hours + 24) % 24;
  return `${String(nextHour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
}

function buildLifecycleForecast(stage, lastValue) {
  if (stage === '潜伏期') return [Math.min(82, lastValue + 14), Math.min(92, lastValue + 24), Math.max(62, lastValue + 16)];
  if (stage === '成长期') return [Math.min(96, lastValue + 12), Math.min(100, lastValue + 20), Math.max(72, lastValue + 8)];
  if (stage === '高潮期') return [Math.max(76, lastValue - 4), Math.max(48, lastValue - 18), Math.max(32, lastValue - 34)];
  return [Math.max(24, lastValue - 12), Math.max(14, lastValue - 24), Math.max(8, lastValue - 34)];
}

function buildStageAreas(xAxis, peakIndex) {
  const lastIndex = xAxis.length - 1;
  const latentEnd = Math.max(1, Math.min(lastIndex, peakIndex - 2));
  const growthEnd = Math.max(latentEnd + 1, Math.min(lastIndex, peakIndex));
  const peakEnd = Math.max(growthEnd + 1, Math.min(lastIndex, peakIndex + 1));
  const segments = [
    { name: '潜伏期', start: 0, end: latentEnd, color: 'rgba(134, 143, 158, 0.1)', labelColor: '#64748B' },
    { name: '成长期', start: latentEnd, end: growthEnd, color: 'rgba(212, 120, 58, 0.1)', labelColor: '#D4783A' },
    { name: '高潮期', start: growthEnd, end: peakEnd, color: 'rgba(201, 63, 69, 0.1)', labelColor: '#C93F45' },
    { name: '衰退期', start: peakEnd, end: lastIndex, color: 'rgba(54, 111, 184, 0.09)', labelColor: '#366FB8' },
  ];

  return segments
    .filter((segment) => segment.end > segment.start)
    .map((segment) => [
      {
        name: segment.name,
        xAxis: xAxis[segment.start],
        itemStyle: { color: segment.color },
        label: {
          color: segment.labelColor,
          fontWeight: 850,
          position: 'insideTop',
          padding: [8, 0, 0, 0],
        },
      },
      { xAxis: xAxis[segment.end] },
    ]);
}

function buildLifecycleOption(event) {
  const trend = event.trend?.length ? event.trend : emptyTrend;
  const maxTrendValue = Math.max(...trend.map((point) => point.value), 1);
  const actual = trend.map((item) => Math.round((item.value / maxTrendValue) * 100));
  const lastActual = actual[actual.length - 1] || 0;
  const peakIndex = actual.reduce((currentIndex, value, index) => (value > actual[currentIndex] ? index : currentIndex), 0);
  const lastTime = trend[trend.length - 1]?.time || '18:00';
  const futureTimes = [2, 4, 6].map((hours) => addHoursToTime(lastTime, hours));
  const forecast = buildLifecycleForecast(event.stage, lastActual);
  const xAxis = [...trend.map((item) => item.time), ...futureTimes];
  const forecastData = [...Array(Math.max(0, actual.length - 1)).fill(null), lastActual, ...forecast];

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) =>
        params
          .filter((item) => item.value !== null && item.value !== undefined)
          .map((item) => `${item.marker}${item.seriesName}<br/>${item.axisValue}：${item.value}`)
          .join('<br/>'),
    },
    legend: { top: 0, right: 12, textStyle: { color: '#444A56' } },
    grid: { top: 48, right: 28, bottom: 34, left: 46 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: xAxis,
      axisLabel: { color: '#868F9E' },
      axisLine: { lineStyle: { color: '#E2E7EF' } },
    },
    yAxis: {
      type: 'value',
      name: '热度指数',
      max: 100,
      axisLabel: { color: '#868F9E' },
      splitLine: { lineStyle: { color: '#E8EEF3' } },
    },
    series: [
      {
        name: '已观测',
        type: 'line',
        smooth: 0.25,
        data: [...actual, null, null, null],
        symbolSize: 7,
        lineStyle: { width: 4, color: '#366FB8' },
        itemStyle: { color: '#366FB8' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(54, 111, 184, 0.24)' },
              { offset: 1, color: 'rgba(54, 111, 184, 0.03)' },
            ],
          },
        },
        markArea: {
          silent: true,
          data: buildStageAreas(xAxis, peakIndex),
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#D4783A', type: 'dashed', width: 1.5 },
          label: { formatter: '当前', color: '#D4783A', fontWeight: 850 },
          data: [{ xAxis: lastTime }],
        },
      },
      {
        name: '预测值',
        type: 'line',
        smooth: 0.25,
        data: forecastData,
        symbolSize: 7,
        lineStyle: { width: 3, color: '#D4783A', type: 'dashed' },
        itemStyle: { color: '#D4783A' },
        areaStyle: { color: 'rgba(212, 120, 58, 0.07)' },
      },
    ],
  };
}

function buildClusterOption() {
  const clusterColors = {
    暴雨救援: '#469B78',
    交通出行: '#4E74BD',
    消费权益: '#C93F45',
    教育民生: '#D4783A',
    医疗民生: '#7962B3',
    公共服务: '#2A3F54',
  };

  return {
    tooltip: {
      formatter: (params) => `${params.data.title}<br/>类别：${params.data.cluster}<br/>热度：${params.data.heat}`,
    },
    grid: { top: 28, right: 26, bottom: 36, left: 42 },
    xAxis: {
      name: '相似度维度 X',
      axisLabel: { color: '#868F9E' },
      splitLine: { lineStyle: { color: '#E8EEF3' } },
    },
    yAxis: {
      name: '相似度维度 Y',
      axisLabel: { color: '#868F9E' },
      splitLine: { lineStyle: { color: '#E8EEF3' } },
    },
    series: [
      {
        type: 'scatter',
        data: clusterPoints.map((item) => ({
          ...item,
          value: [item.x, item.y, item.heat],
          itemStyle: { color: clusterColors[item.cluster] || '#4E74BD' },
        })),
        symbolSize: (value) => 14 + value[2] / 3,
        label: {
          show: true,
          formatter: (params) => params.data.cluster,
          position: 'top',
          color: '#444A56',
          fontWeight: 760,
        },
      },
    ],
  };
}

const propagationRoleMeta = [
  { name: '初始爆料', color: '#C93F45' },
  { name: '大V', color: '#D4783A' },
  { name: '官媒', color: '#366FB8' },
  { name: '传播高峰', color: '#7962B3' },
  { name: '普通网民', color: '#868F9E' },
];

const propagationRoleDescriptions = {
  初始爆料: '现场信息源',
  大V: '高影响账号转发',
  官媒: '权威媒体介入',
  传播高峰: '讨论量峰值',
  普通网民: '普通用户扩散',
};

function getPropagationRole(node, index) {
  const name = node.name || '';
  const role = String(node.role || '').trim();
  if (/初始|首发|爆料/.test(role) || node.category === 0 || (!role && index === 0 && /爆料|求助|反馈|投诉|长文|帖子|截图|患者|车主|乘客|游客|居民/.test(name))) return '初始爆料';
  if (/高峰|峰值/.test(role) || node.category === 3) return '传播高峰';
  if (/大V|意见领袖/.test(role) || node.category === 1 || /博主|大V|热搜|社区|短视频|论坛|账号|群|校园号/.test(name)) return '大V';
  if (/官方|媒体|通报/.test(role) || /官方|部门|公告|通报|说明|客服|校方|医院|运营方|平台|考试院|供水|物业|文旅|交通|媒体|新闻|专家/.test(name) || node.category === 2) return '官媒';
  return '普通网民';
}

function formatPropagationTime(value) {
  const text = String(value || '').trim();
  if (!text) return '时间未知';
  return text.replace('T', ' ').slice(0, 16);
}

function formatPropagationAxisTime(value, index) {
  const time = formatPropagationTime(value);
  if (time === '时间未知') return `节点${index + 1}`;
  return `${time.slice(5, 10)}\n${time.slice(11, 16)}`;
}

function formatPropagationInfluence(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return '暂无';
  return number >= 100 ? number.toFixed(1) : number.toFixed(1).replace(/\.0$/, '');
}

function buildTraceSequenceOption(event) {
  const nodes = event.pathNodes.map((node, index) => {
    const role = getPropagationRole(node, index);
    const roleIndex = propagationRoleMeta.findIndex((item) => item.name === role);
    const multiplier = { 初始爆料: 0.95, 大V: 1.35, 官媒: 1.62, 普通网民: 0.62 }[role] || 1;
    const rawInfluence = Number(node.influence);
    const influence = Number.isFinite(rawInfluence) && rawInfluence > 0
      ? rawInfluence
      : Math.round(((node.symbolSize || 38) * 120 + event.heat * 16) * multiplier);
    const publishTime = node.publish_time || node.publishTime || '';
    const axisTime = formatPropagationAxisTime(publishTime, index);

    return {
      id: node.name,
      name: node.name,
      role,
      index,
      axisTime,
      category: Math.max(0, roleIndex),
      value: [axisTime, role],
      influence,
      platform: node.platform || '',
      publishTime,
      influenceLabel: formatPropagationInfluence(rawInfluence),
      labelDetail: propagationRoleDescriptions[role] || '传播节点',
      symbolSize: Math.min(76, Math.max(30, Number(node.symbolSize || node.symbol_size || 42))),
      itemStyle: { color: propagationRoleMeta[Math.max(0, roleIndex)]?.color || '#868F9E' },
      label: { fontSize: Number(node.symbolSize || node.symbol_size || 42) > 58 ? 14 : 12 },
    };
  });
  const axisTimes = nodes.map((node) => node.axisTime);
  const arrowLinks = nodes.slice(1).map((node, index) => {
    const source = nodes[index];
    return {
      coords: [
        [source.axisTime, source.role],
        [node.axisTime, node.role],
      ],
      lineStyle: {
        curveness: index % 2 === 0 ? 0.34 : -0.26,
      },
    };
  });

  return {
    color: propagationRoleMeta.map((item) => item.color),
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        if (params.seriesName !== '关键节点') return '';
        const platform = params.data.platform ? `<br/>平台：${params.data.platform}` : '';
        return `${params.data.index + 1}. ${params.name}<br/>角色：${params.data.role}${platform}<br/>时间：${formatPropagationTime(params.data.publishTime)}<br/>影响力：${params.data.influenceLabel}`;
      },
    },
    grid: { top: 28, right: 36, bottom: 64, left: 86 },
    xAxis: {
      type: 'category',
      boundaryGap: true,
      data: axisTimes,
      axisLine: { lineStyle: { color: '#DDE7EC' } },
      axisTick: { alignWithLabel: true, lineStyle: { color: '#DDE7EC' } },
      axisLabel: {
        color: '#667085',
        fontWeight: 720,
        lineHeight: 16,
        hideOverlap: true,
      },
    },
    yAxis: {
      type: 'category',
      data: propagationRoleMeta.map((item) => item.name),
      axisLine: { lineStyle: { color: '#DDE7EC' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#667085',
        fontWeight: 720,
      },
      splitLine: { lineStyle: { color: '#EEF2F6' } },
    },
    series: [
      {
        name: '传播弧线',
        type: 'line',
        data: nodes.map((node) => ({ value: [node.axisTime, node.role] })),
        smooth: 0.5,
        symbol: 'none',
        lineStyle: {
          color: '#7962B3',
          width: 2.2,
          opacity: 0.34,
          cap: 'round',
        },
        z: 1,
        silent: true,
      },
      {
        name: '传播方向',
        type: 'lines',
        coordinateSystem: 'cartesian2d',
        data: arrowLinks,
        symbol: ['none', 'arrow'],
        symbolSize: [0, 14],
        lineStyle: {
          color: '#7962B3',
          width: 2.6,
          opacity: 0.72,
          curveness: 0.32,
          cap: 'round',
        },
        z: 2,
        silent: true,
      },
      {
        name: '关键节点',
        type: 'scatter',
        data: nodes,
        symbolSize: (value, params) => params.data.symbolSize,
        itemStyle: {
          color: (params) => params.data.itemStyle.color,
          borderColor: '#fff',
          borderWidth: 2,
          shadowBlur: 10,
          shadowColor: 'rgba(42, 63, 84, 0.16)',
        },
        label: {
          show: true,
          formatter: (params) => `{title|${params.data.index + 1}. ${params.data.role}}\n{desc|${params.data.labelDetail}}`,
          position: 'top',
          distance: 12,
          color: '#1A1F27',
          fontWeight: 850,
          fontSize: 12,
          lineHeight: 18,
          backgroundColor: 'rgba(255, 255, 255, 0.92)',
          borderColor: 'rgba(226, 231, 239, 0.9)',
          borderWidth: 1,
          borderRadius: 6,
          padding: [5, 8],
          rich: {
            title: {
              color: '#1A1F27',
              fontSize: 12,
              fontWeight: 850,
              lineHeight: 18,
            },
            desc: {
              color: '#667085',
              fontSize: 11,
              fontWeight: 720,
              lineHeight: 16,
            },
          },
        },
        emphasis: {
          scale: true,
          label: { color: '#2A3F54' },
        },
        z: 3,
      },
    ],
  };
}

function buildPlatformRoseOption(event) {
  return {
    color: ['#2A3F54', '#366FB8', '#3A9477', '#D4783A', '#7962B3'],
    tooltip: { trigger: 'item', formatter: '{b}<br/>报道占比：{d}%' },
    legend: {
      bottom: 0,
      icon: 'circle',
      textStyle: { color: '#444A56' },
    },
    series: [
      {
        name: '平台分布',
        type: 'pie',
        roseType: 'radius',
        radius: ['20%', '72%'],
        center: ['50%', '43%'],
        avoidLabelOverlap: true,
        label: {
          color: '#1A1F27',
          formatter: '{b}\n{d}%',
        },
        labelLine: {
          length: 14,
          length2: 10,
          lineStyle: { color: '#868F9E' },
        },
        data: event.platforms,
      },
    ],
  };
}

function normalizeOfficialSourceRatio(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return Math.max(0, Math.min(100, number > 0 && number <= 1 ? Math.round(number * 100) : Math.round(number)));
}

function authenticityTone(ratio) {
  if (ratio === null) return 'pending';
  if (ratio >= 60) return 'ok';
  if (ratio >= 20) return 'warn';
  return 'danger';
}

function plainUserTone(ratio) {
  if (ratio === null) return 'pending';
  if (ratio <= 30) return 'ok';
  if (ratio <= 60) return 'warn';
  return 'danger';
}

function buildAuthenticityRatioChecks(authenticity = {}) {
  const ratios = [
    {
      key: 'official_ratio',
      aliases: ['official_ratio', 'officialRatio'],
      topic: '官方来源比例',
      label: '官方来源',
      tone: authenticityTone,
      verdict: (ratio) => `官方来源占比 ${ratio}%，用于判断该事件是否已有权威信源覆盖。`,
    },
    {
      key: 'verified_ratio',
      aliases: ['verified_ratio', 'verifiedRatio'],
      topic: '已认证来源比例',
      label: '已认证来源',
      tone: authenticityTone,
      verdict: (ratio) => `已认证来源占比 ${ratio}%，用于衡量可追溯账号或机构来源的覆盖程度。`,
    },
    {
      key: 'plain_user_ratio',
      aliases: ['plain_user_ratio', 'plainUserRatio'],
      topic: '普通用户比例',
      label: '普通用户',
      tone: plainUserTone,
      verdict: (ratio) => `普通用户来源占比 ${ratio}%，占比越高越需要继续交叉核验。`,
    },
  ];

  return ratios
    .map((item) => {
      const sourceValue = item.aliases.map((key) => authenticity[key]).find((value) => value !== undefined && value !== null && value !== '');
      const ratio = normalizeOfficialSourceRatio(sourceValue);
      if (ratio === null) return null;
      return {
        topic: item.topic,
        label: item.label,
        officialRatio: ratio,
        tone: item.tone(ratio),
        verdict: item.verdict(ratio),
      };
    })
    .filter(Boolean);
}

function buildFakeChecks(event) {
  const authenticity = event.authenticity || {};
  const rawTopics = authenticity.topics || authenticity.subtopics || authenticity.checks || authenticity.items || [];
  const topics = Array.isArray(rawTopics) ? rawTopics : [];
  const ratioChecks = buildAuthenticityRatioChecks(authenticity);

  if (ratioChecks.length) return ratioChecks;

  if (!topics.length) {
    return [
      {
        topic: '六蓝水库附近村庄受灾',
        label: '官方来源',
        officialRatio: 62,
        tone: 'ok',
        verdict: '来源多元，已有官方和主流媒体信源交叉覆盖。',
      },
      {
        topic: '水库系豆腐渣工程',
        label: '官方来源',
        officialRatio: 0,
        tone: 'warn',
        verdict: '仅见社交媒体传播，暂未发现官方信源支撑。',
      },
      {
        topic: '动物园锁死猛兽',
        label: '官方来源',
        officialRatio: 15,
        tone: 'warn',
        verdict: '存在争议回应，但权威来源覆盖不足，建议继续核验。',
      },
      {
        topic: '辟谣：相关不实说法',
        label: '官方来源',
        officialRatio: 85,
        tone: 'info',
        verdict: '辟谣性质明确，官方信源覆盖较高，可作为低风险线索处理。',
      },
    ];
  }

  return topics.map((item, index) => {
    const ratio = normalizeOfficialSourceRatio(
      item.official_source_ratio ?? item.officialSourceRatio ?? item.official_ratio ?? item.source_ratio ?? item.ratio,
    );
    return {
      topic: item.topic || item.title || item.name || `子议题 ${index + 1}`,
      label: item.label || item.source_label || item.sourceLabel || '官方来源',
      officialRatio: ratio,
      tone: item.tone || authenticityTone(ratio),
      verdict: item.evaluation || item.verdict || item.summary || item.comment || '该子议题暂未返回核验评价。',
    };
  });
}

export default function EventDetailPage() {
  const { id } = useParams();
  const chartInstancesRef = useRef(new Map());
  const fallbackEvent = useMemo(() => resolveFallbackEvent(id), [id]);
  const backendMode = isBackendMode();
  const initialDeferredContent = useMemo(() => getInitialDeferredContent(fallbackEvent, !backendMode), [backendMode, fallbackEvent]);
  const [baseEvent, setBaseEvent] = useState(() => buildBaseEvent(fallbackEvent));
  const [similarEvents, setSimilarEvents] = useState(initialDeferredContent.similarEvents);
  const [adviceContent, setAdviceContent] = useState({
    advice: initialDeferredContent.advice,
    adviceItems: initialDeferredContent.adviceItems,
  });
  const [similarStatus, setSimilarStatus] = useState('idle');
  const [adviceStatus, setAdviceStatus] = useState('idle');
  const [similarError, setSimilarError] = useState('');
  const [adviceError, setAdviceError] = useState('');
  const [detailError, setDetailError] = useState('');
  const [isExportingBrief, setIsExportingBrief] = useState(false);

  useEffect(() => {
    let alive = true;
    const initialDeferred = getInitialDeferredContent(fallbackEvent, !backendMode);

    setDetailError('');
    setBaseEvent(buildBaseEvent(fallbackEvent));
    setSimilarEvents(initialDeferred.similarEvents);
    setAdviceContent({
      advice: initialDeferred.advice,
      adviceItems: initialDeferred.adviceItems,
    });
    setSimilarError('');
    setAdviceError('');
    setSimilarStatus(api.getEventSimilarEvents ? 'loading' : 'success');
    setAdviceStatus(api.getEventAdvice ? 'loading' : 'success');

    api
      .getEventDetail(id)
      .then((nextEvent) => {
        if (!alive) return;
        setBaseEvent(buildBaseEvent(fallbackEvent, nextEvent));
      })
      .catch((error) => {
        if (!alive) return;
        setDetailError(error.message || '事件详情加载失败');
        setBaseEvent(buildBaseEvent(fallbackEvent));
      });

    if (api.getEventSimilarEvents) {
      api
        .getEventSimilarEvents(id)
        .then((items) => {
          if (!alive) return;
          setSimilarEvents(items || []);
          setSimilarStatus('success');
        })
        .catch((error) => {
          if (!alive) return;
        setSimilarError(error.message || '相似事件加载失败');
          setSimilarStatus('error');
        });
    }

    if (api.getEventAdvice) {
      api
        .getEventAdvice(id)
        .then((advice) => {
          if (!alive) return;
          setAdviceContent({
            advice: advice?.advice || '',
            adviceItems: advice?.adviceItems || [],
          });
          setAdviceStatus('success');
        })
        .catch((error) => {
          if (!alive) return;
          setAdviceError(error.message || '处置建议加载失败');
          setAdviceStatus('error');
        });
    }

    return () => {
      alive = false;
    };
  }, [backendMode, fallbackEvent, id]);
  const event = useMemo(
    () => ({
      ...baseEvent,
      similarEvents,
      advice: adviceContent.advice,
      adviceItems: adviceContent.adviceItems,
    }),
    [adviceContent.advice, adviceContent.adviceItems, baseEvent, similarEvents],
  );
  const visibleTrend = useMemo(() => buildVisibleTrend(event.trend), [event.trend]);
  const trendOption = useMemo(() => buildTrendOption(visibleTrend), [visibleTrend]);
  const sentimentOption = useMemo(() => buildPieOption(event), [event]);
  const platformBarOption = useMemo(() => buildPlatformBarOption(event), [event]);
  const lifecycleOption = useMemo(() => buildLifecycleOption(event), [event]);
  const traceSequenceOption = useMemo(() => buildTraceSequenceOption(event), [event]);
  const authenticityTopics = useMemo(() => buildFakeChecks(event), [event]);
  const discussionCount = Math.round(event.reportCount * (event.sentiment.negative + event.heat) * 0.18);
  const eventContextTag = useMemo(() => getEventContextTag(event), [event.category, event.location]);
  const eventLocationText = useMemo(() => getVisibleEventLocation(event.location) || '暂无地点信息', [event.location]);
  const setChartInstance = useCallback((chartId, title, instance) => {
    if (!instance) {
      chartInstancesRef.current.delete(chartId);
      return;
    }
    chartInstancesRef.current.set(chartId, { id: chartId, title, instance });
  }, []);
  const chartReadyHandlers = useMemo(
    () => ({
      trend: (instance) => setChartInstance('trend', '报道发展趋势', instance),
      platform: (instance) => setChartInstance('platform', '平台数据分布', instance),
      sentiment: (instance) => setChartInstance('sentiment', '情绪分布', instance),
      lifecycle: (instance) => setChartInstance('lifecycle', '阶段判断与趋势预测', instance),
      trace: (instance) => setChartInstance('trace', '关键传播节点', instance),
    }),
    [setChartInstance],
  );

  const captureChartImages = useCallback(async () => {
    window.dispatchEvent(new Event('resize'));
    await new Promise((resolve) => {
      window.requestAnimationFrame(() => window.requestAnimationFrame(resolve));
    });

    return Array.from(chartInstancesRef.current.values())
      .map(({ id: chartId, title, instance }) => {
        try {
          instance.resize();
          if (!instance.getWidth() || !instance.getHeight()) return null;
          return {
            id: chartId,
            title,
            data_url: instance.getDataURL({
              type: 'png',
              pixelRatio: 2,
              backgroundColor: '#ffffff',
            }),
          };
        } catch (error) {
          console.warn(`图表 ${title} 导出失败`, error);
          return null;
        }
      })
      .filter(Boolean);
  }, []);

  const exportReport = async () => {
    if (isExportingBrief) return;

    const timestamp = buildTimestamp();
    const titlePart = sanitizeFilePart(event.title, '未命名事件').slice(0, 18);
    setIsExportingBrief(true);
    try {
      const charts = await captureChartImages();
      await postPdfToBackend(
        `/api/events/${event.id}/brief-with-charts.pdf`,
        { charts },
        `Trendsight-事件简报-${titlePart}-${timestamp}.pdf`,
      );
    } catch (error) {
      console.error(error);
      window.alert(`导出事件简报失败：${error.message || '请确认数据服务可用'}`);
    } finally {
      setIsExportingBrief(false);
    }
  };

  return (
    <AppShell wide>
      <section className="detail-workspace">
        <div className="detail-report-main">
          <article className="report-hero-card">
            <Link to="/dashboard" className="back-link">
              <ArrowLeft size={16} />
              返回看板
            </Link>
            {detailError && <p className="detail-load-error">{detailError}</p>}
            <div className="event-status-row">
              <span className={stageClass[event.stage] || 'stage-growth'}>{event.stage}</span>
              <span className={riskClass[event.risk] || 'risk-mid'}>风险 {event.risk}</span>
              {eventContextTag ? <span>{eventContextTag}</span> : null}
            </div>
            <div className="report-hero-main">
              <div>
                <h1>{event.title}</h1>
                <p>{event.summary}</p>
              </div>
              <div className="report-export-actions">
                <button type="button" onClick={exportReport} disabled={isExportingBrief} aria-busy={isExportingBrief}>
                  {isExportingBrief ? <Loader2 className="button-spinner" size={18} /> : <Download size={18} />}
                  {isExportingBrief ? '生成中...' : '导出简报'}
                </button>
              </div>
            </div>
            <div className="detail-kpi-strip">
              <KpiItem label="热度指数" value={event.heat} icon={Flame} tone="orange" />
              <KpiItem label="累计报道" value={formatCount(event.reportCount)} icon={FileCheck2} tone="blue" />
              <KpiItem label="参与讨论" value={formatCount(discussionCount)} icon={Network} tone="violet" />
              <KpiItem label="可信度" value={`${Math.round(event.falseConfidence * 100)}%`} icon={ShieldCheck} tone="green" />
            </div>
          </article>

          <nav className="detail-anchor-nav" aria-label="报告章节导航">
            <a href="#overview">概述</a>
            <a href="#trend">趋势</a>
            <a href="#platform">平台</a>
            <a href="#sentiment">情绪</a>
            <a href="#wordcloud">词云</a>
            <a href="#lifecycle">阶段预测</a>
            <a href="#trace">传播节点</a>
            <a href="#authenticity">可信度</a>
            <a href="#retrieval">相似事件</a>
            <a href="#advice">处置建议</a>
          </nav>

          <ReportSection id="overview" label="Overview" title="事件概述">
            <div className="fact-grid">
              <FactItem label="发生时间" value={event.time} />
              <FactItem label="发生地点" value={eventLocationText} />
              <FactItem label="直接起因" value={event.cause} />
              <FactItem label="涉事主体" value={event.people} />
            </div>
            <p className="report-paragraph">{event.summary}</p>
          </ReportSection>

          <ReportSection id="trend" label="Trend" title="报道发展趋势">
            <EChart option={trendOption} className="report-trend-chart" onReady={chartReadyHandlers.trend} />
            <TrendEventAxis trend={visibleTrend} />
          </ReportSection>

          <ReportSection id="platform" label="Platform" title="平台数据分布">
            <EChart option={platformBarOption} className="platform-bar-chart" onReady={chartReadyHandlers.platform} />
          </ReportSection>

          <section className="analysis-split">
            <ReportSection id="sentiment" label="情绪" title="情绪分布">
              <div className="sentiment-detail-grid">
                <EChart option={sentimentOption} className="sentiment-donut-chart" onReady={chartReadyHandlers.sentiment} />
                <SentimentBar sentiment={event.sentiment} />
              </div>
            </ReportSection>

            <ReportSection id="wordcloud" label="关键词" title="高频关键词">
              <WordCloud words={event.words} getColor={getKeywordColor} />
            </ReportSection>
          </section>

          <ReportSection id="lifecycle" label="阶段" title="阶段判断与趋势预测">
            <div className="lifecycle-stage-row">
              {['潜伏期', '成长期', '高潮期', '衰退期'].map((stage) => (
                <span className={stage === event.stage ? 'active' : ''} key={stage}>
                  {stage}
                </span>
              ))}
            </div>
            <EChart option={lifecycleOption} className="lifecycle-chart" onReady={chartReadyHandlers.lifecycle} />
          </ReportSection>

          <ReportSection id="trace" label="传播" title="关键传播节点">
            <EChart option={traceSequenceOption} className="trace-sequence-chart" onReady={chartReadyHandlers.trace} />
            <PropagationNodeDetails event={event} />
          </ReportSection>

          <ReportSection id="authenticity" label="核验" title="可信度核验">
            {(event.authenticityLabel || event.authenticityDescription) && (
              <div className={`auth-summary ${event.authenticityLevel || 'pending'}`}>
                <div>
                  <span>综合可信度</span>
                  <b>{event.authenticityLabel || '待核验'}</b>
                </div>
                {event.authenticityDescription && <p>{event.authenticityDescription}</p>}
              </div>
            )}
            <div className="auth-topic-list">
              {authenticityTopics.map((item) => (
                <article className={`auth-topic-card ${item.tone}`} key={item.topic}>
                  <div className="auth-topic-head">
                    <span>{item.topic}</span>
                      <b>{item.officialRatio === null ? `${item.label || '官方来源'}暂无数据` : `${item.label || '官方来源'} ${item.officialRatio}%`}</b>
                  </div>
                  <div className="official-source-meter" aria-label={`${item.topic} ${item.label || '官方来源'}占比`}>
                    <span style={{ width: `${item.officialRatio ?? 0}%` }} />
                  </div>
                  <p>{item.verdict}</p>
                </article>
              ))}
            </div>
          </ReportSection>

          <section className="analysis-split bottom">
            <ReportSection id="retrieval" label="历史对比" title="相似历史事件">
              <SimilarEventsContent status={similarStatus} error={similarError} items={event.similarEvents} />
            </ReportSection>

            <ReportSection id="advice" label="建议" title="处置建议">
            <AdviceContent status={adviceStatus} error={adviceError} advice={event.advice} adviceItems={event.adviceItems} />
          </ReportSection>
          </section>
        </div>

        <aside className="detail-assistant-panel">
          <QAPanel event={event} compact />
        </aside>
      </section>
    </AppShell>
  );
}

function ReportSection({ id, title, children }) {
  return (
    <article className="report-section-card" id={id}>
      <div className="report-section-title">
        <h2>{title}</h2>
      </div>
      {children}
    </article>
  );
}

function FactItem({ label, value }) {
  return (
    <div className="fact-item">
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}

function KpiItem({ label, value, icon: Icon, tone }) {
  return (
    <div className="detail-kpi-item">
      <Icon className={tone} size={20} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PropagationNodeDetails({ event }) {
  const keyNodes = event.propagation?.keyNodes?.length ? event.propagation.keyNodes : event.pathNodes || [];
  const topInfluencers = event.propagation?.topInfluencers || [];

  if (!keyNodes.length) {
    return <p className="deferred-load-state">暂无关键传播节点数据。</p>;
  }

  return (
    <div className="propagation-detail-grid">
      <div className="propagation-node-list">
        <h3>节点明细</h3>
        {keyNodes.map((node, index) => (
          <article className="propagation-node-item" key={`${node.role || node.name}-${node.author || index}-${node.publish_time || node.publishTime || index}`}>
            <span>{index + 1}</span>
            <div>
              <strong>{node.role || getPropagationRole(node, index)}</strong>
              <p>{node.title || node.name}</p>
              <small>
                {[node.author, node.platform, formatPropagationTime(node.publish_time || node.publishTime)].filter(Boolean).join(' · ')}
              </small>
            </div>
            <b>{formatPropagationInfluence(node.influence)}</b>
          </article>
        ))}
      </div>

      <div className="propagation-influencer-list">
        <h3>高影响账号</h3>
        {topInfluencers.length ? (
          topInfluencers.slice(0, 3).map((item, index) => (
            <article className="propagation-influencer-item" key={`${item.author || index}-${item.publishTime || item.publish_time || index}`}>
              <div>
                <strong>{item.author || '匿名账号'}</strong>
                <span>{item.platform || '未知平台'}</span>
              </div>
              <p>{item.title || '暂无内容摘要'}</p>
              <b>影响力 {formatPropagationInfluence(item.influence)}</b>
            </article>
          ))
        ) : (
          <p className="deferred-load-state">暂无高影响账号数据。</p>
        )}
      </div>
    </div>
  );
}

function SimilarEventsContent({ status, error, items }) {
  if (status === 'loading') {
    return (
      <div className="similar-list" aria-busy="true" aria-label="历史相似事件加载中">
        <DeferredSkeletonRow />
        <DeferredSkeletonRow />
        <DeferredSkeletonRow />
      </div>
    );
  }

  if (status === 'error') {
    return <p className="deferred-load-state error">{error || '相似历史事件加载失败，请稍后重试。'}</p>;
  }

  if (!items.length) {
    return <p className="deferred-load-state">没有匹配到相似历史事件。</p>;
  }

  return (
    <div className="similar-list">
      {items.map((item, index) => {
        const similarEvent = normalizeSimilarEventItem(item, index);
        return (
          <article className="similar-event-item" key={similarEvent.key}>
            <div>
              <b>{similarEvent.title}</b>
              {similarEvent.similarityLabel && <span>{similarEvent.similarityLabel}</span>}
            </div>
            {similarEvent.reason && <p>{similarEvent.reason}</p>}
          </article>
        );
      })}
    </div>
  );
}

function AdviceContent({ status, error, advice, adviceItems }) {
  if (status === 'loading') {
    return (
      <div className="advice-grid" aria-busy="true" aria-label="处置建议加载中">
        <DeferredSkeletonRow />
        <DeferredSkeletonRow />
        <DeferredSkeletonRow />
      </div>
    );
  }

  if (status === 'error') {
    return <p className="deferred-load-state error">{error || '处置建议加载失败，稍后可重试。'}</p>;
  }

  if (adviceItems?.length) {
    return (
      <div className="advice-grid">
        {adviceItems.map((item) => (
          <article className="advice-item" key={item.label}>
            <span>{item.label}</span>
            <p>{item.text}</p>
          </article>
        ))}
      </div>
    );
  }

  return <p className="report-paragraph">{advice || '还没有处置建议。'}</p>;
}

function DeferredSkeletonRow() {
  return (
    <div className="deferred-skeleton-row">
      <span />
      <span />
    </div>
  );
}

function TrendEventAxis({ trend }) {
  return (
    <div className="trend-event-axis" style={{ gridTemplateColumns: `repeat(${trend.length}, minmax(0, 1fr))` }}>
      {trend.map((item, index) => (
        <div className={`trend-event-slot ${item.node ? 'has-event' : ''}`} key={`${item.time}-${index}`}>
          <span>{item.time}</span>
          {item.node && (
            <p>
              <i />
              {item.node}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
