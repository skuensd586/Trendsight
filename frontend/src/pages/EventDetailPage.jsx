import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Download, FileCheck2, Flame, Network, ShieldCheck, Tags } from 'lucide-react';
import AppShell from '../components/AppShell.jsx';
import EChart from '../components/EChart.jsx';
import QAPanel from '../components/QAPanel.jsx';
import SentimentBar from '../components/SentimentBar.jsx';
import WordCloud from '../components/WordCloud.jsx';
import { api, isBackendMode } from '../api/index.js';
import { events } from '../data/events.js';
import { clusterPoints, propagationSankey } from '../data/mockAnalytics.js';
import { buildTimestamp, downloadPdfFromBackend, sanitizeFilePart } from '../utils/briefExport.js';

const chartColors = ['#469B78', '#4E74BD', '#C93F45', '#D4783A', '#7962B3'];
const defaultGeoDiscussion = [
  { name: '广东省', displayName: '广东', lng: 113.27, lat: 23.13, value: 124000 },
  { name: '广西壮族自治区', displayName: '广西', lng: 108.32, lat: 22.82, value: 82000 },
  { name: '福建省', displayName: '福建', lng: 119.3, lat: 26.08, value: 68000 },
  { name: '湖南省', displayName: '湖南', lng: 112.98, lat: 28.19, value: 54000 },
  { name: '江西省', displayName: '江西', lng: 115.86, lat: 28.68, value: 42000 },
  { name: '上海市', displayName: '上海', lng: 121.47, lat: 31.23, value: 39000 },
  { name: '北京市', displayName: '北京', lng: 116.4, lat: 39.9, value: 31000 },
  { name: '四川省', displayName: '四川', lng: 104.07, lat: 30.67, value: 26000 },
  { name: '陕西省', displayName: '陕西', lng: 108.94, lat: 34.34, value: 18000 },
];
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

function createEmptyDetailEvent(id = '') {
  return {
    id: String(id || ''),
    title: '事件详情加载中',
    category: '未分类',
    time: '',
    location: '未标注地区',
    cause: '暂无后端详情数据',
    people: '暂无',
    summary: '正在加载后端事件详情。',
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
    advice: '暂无处置建议。',
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
    title: item?.title || '未命名相似事件',
    similarityLabel,
    reason: item?.reason || '',
  };
}

function buildTrendOption(event) {
  const trend = event.trend?.length ? event.trend : emptyTrend;
  const trendData = trend.map((item) => item.value);
  const peak = trend.reduce((current, item) => (item.value > current.value ? item : current), trend[0]);
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
      name: '报道量 / 条',
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
          data: [[{ xAxis: event.trend[3]?.time || '12:00' }, { xAxis: event.trend[5]?.time || '16:00' }]],
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

function formatGeoValue(value) {
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`;
  return value.toLocaleString();
}

function buildGeoHeatOption(event) {
  const geoDiscussion = event.geoDiscussion?.length ? event.geoDiscussion : defaultGeoDiscussion;
  const values = geoDiscussion.map((item) => item.value);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const provinceData = geoDiscussion.map((item) => ({ name: item.name, value: item.value }));
  const pointData = geoDiscussion.map((item) => ({
    name: item.displayName || item.name,
    value: [item.lng, item.lat, item.value],
  }));

  return {
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const value = Array.isArray(params.value) ? params.value[2] : params.value;
        return `${params.name}<br/>讨论量：${value ? formatGeoValue(value) : '暂无数据'}`;
      },
    },
    visualMap: {
      min,
      max,
      left: 16,
      bottom: 14,
      calculable: true,
      itemWidth: 10,
      itemHeight: 96,
      text: ['高', '低'],
      textStyle: { color: '#868F9E' },
      inRange: {
        color: ['#EAF1F4', '#CDE5DF', '#D9AE73', '#C93F45'],
      },
    },
    geo: {
      map: 'china',
      roam: false,
      zoom: 1.28,
      layoutCenter: ['52%', '54%'],
      layoutSize: '86%',
      label: { show: false },
      itemStyle: {
        areaColor: '#F2F6F7',
        borderColor: '#DDE7EC',
        borderWidth: 1,
      },
      emphasis: {
        label: { show: false },
        itemStyle: { areaColor: '#CDE5DF' },
      },
    },
    series: [
      {
        name: '讨论热度',
        type: 'map',
        map: 'china',
        geoIndex: 0,
        data: provinceData,
      },
      {
        name: '核心讨论区',
        type: 'effectScatter',
        coordinateSystem: 'geo',
        data: pointData
          .slice()
          .sort((first, second) => second.value[2] - first.value[2])
          .slice(0, 6),
        symbolSize: (value) => 10 + (value[2] / max) * 28,
        rippleEffect: { brushType: 'stroke', scale: 3.2 },
        itemStyle: {
          color: '#C93F45',
          shadowBlur: 12,
          shadowColor: 'rgba(201, 63, 69, 0.28)',
        },
        label: {
          show: true,
          formatter: (params) => params.name,
          position: 'right',
          color: '#1A1F27',
          fontSize: 12,
          fontWeight: 760,
        },
      },
    ],
  };
}

function buildPieOption(event) {
  const sentimentData = [
    { name: '积极', value: event.sentiment.positive },
    { name: '中性', value: event.sentiment.neutral },
    { name: '消极', value: event.sentiment.negative },
  ];
  const dominant = sentimentData.reduce((current, item) => (item.value > current.value ? item : current), sentimentData[0]);
  const conclusion = dominant.name === '积极' ? '情绪偏正向' : dominant.name === '消极' ? '负面需关注' : '中性占主导';

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
        color: dominant.name === '积极' ? '#469B78' : dominant.name === '消极' ? '#C93F45' : '#4E74BD',
        fontSize: 20,
        fontWeight: 900,
      },
    },
    legend: { show: false },
    series: [
      {
        name: '情感分布',
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
        return `${params.name}<br/>词频权重：${params.value}`;
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
    tooltip: { formatter: (params) => `${params.name}<br/>词频权重：${params.value || ''}` },
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

function buildKeywordRankOption(event) {
  const words = event.words?.length ? event.words : emptyWords;
  const ranked = words.slice(0, 8).reverse();
  const max = Math.max(...ranked.map(([, weight]) => weight), 1);

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => `${params[0].name}<br/>TF-IDF 权重：${params[0].value}`,
    },
    grid: { top: 12, right: 48, bottom: 20, left: 62 },
    xAxis: {
      type: 'value',
      max: Math.ceil(max / 10) * 10,
      axisLabel: { color: '#868F9E' },
      splitLine: { lineStyle: { color: '#E8EEF3' } },
    },
    yAxis: {
      type: 'category',
      data: ranked.map(([word]) => word),
      axisLabel: { color: '#1A1F27', fontWeight: 820 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'bar',
        data: ranked.map(([word, weight]) => ({
          value: weight,
          itemStyle: {
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
        })),
        barWidth: 16,
        label: {
          show: true,
          position: 'right',
          formatter: '{c}',
          color: '#444A56',
          fontWeight: 850,
        },
        itemStyle: {
          borderRadius: [0, 8, 8, 0],
        },
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

function buildThemeRiverOption(event) {
  const themes = [
    { name: '暴雨', weight: [0.44, 0.5, 0.42, 0.25, 0.18, 0.16, 0.12] },
    { name: '救援', weight: [0.18, 0.24, 0.34, 0.42, 0.46, 0.38, 0.3] },
    { name: '积水', weight: [0.28, 0.32, 0.3, 0.24, 0.2, 0.16, 0.12] },
    { name: '路况', weight: [0.08, 0.12, 0.2, 0.24, 0.26, 0.28, 0.3] },
    { name: '通报', weight: [0.02, 0.05, 0.08, 0.18, 0.24, 0.28, 0.32] },
  ];
  const trend = event.trend?.length ? event.trend : emptyTrend;
  const data = trend.flatMap((point, index) =>
    themes.map((theme) => {
      const weight = theme.weight[index] ?? theme.weight[theme.weight.length - 1] ?? 0.1;
      const time = /^\d{4}-\d{2}-\d{2}/.test(point.time) ? point.time.replace(/-/g, '/') : `2026/07/07 ${point.time || '00:00'}`;
      return [time, Math.max(12, Math.round(point.value * weight)), theme.name];
    }),
  );

  return {
    color: ['#2A3F54', '#366FB8', '#3A9477', '#4D8A91', '#72A7B5'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { color: '#444A56' } },
    singleAxis: {
      top: 54,
      bottom: 28,
      type: 'time',
      axisLabel: {
        color: '#868F9E',
        formatter: (value) => new Date(value).getHours().toString().padStart(2, '0') + ':00',
      },
      axisLine: { lineStyle: { color: '#E2E7EF' } },
    },
    series: [
      {
        type: 'themeRiver',
        emphasis: { itemStyle: { shadowBlur: 12, shadowColor: 'rgba(42,63,84,0.18)' } },
        data,
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
        name: 'AI预测',
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
      formatter: (params) => `${params.data.title}<br/>聚类：${params.data.cluster}<br/>热度：${params.data.heat}`,
    },
    grid: { top: 28, right: 26, bottom: 36, left: 42 },
    xAxis: {
      name: '语义相似维度 X',
      axisLabel: { color: '#868F9E' },
      splitLine: { lineStyle: { color: '#E8EEF3' } },
    },
    yAxis: {
      name: '语义相似维度 Y',
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
  { name: '普通网民', color: '#868F9E' },
];

function getPropagationRole(node, index) {
  const name = node.name || '';
  if (index === 0 || node.category === 0 || /爆料|求助|反馈|投诉|长文|帖子|截图|患者|车主|乘客|游客|居民/.test(name)) return '初始爆料';
  if (/官方|部门|公告|通报|说明|客服|校方|医院|运营方|平台|考试院|供水|物业|文旅|交通|媒体|新闻|专家/.test(name) || node.category === 2 || node.category === 3) return '官媒';
  if (node.category === 1 || /博主|大V|热搜|社区|短视频|论坛|账号|群|校园号/.test(name)) return '大V';
  return '普通网民';
}

function buildTraceForceOption(event) {
  const timelineData = event.trend.map((item) => item.time);
  const arrivalStep = Math.max(1, Math.floor(timelineData.length / Math.max(1, event.pathNodes.length - 1)));
  const nodeArrivalMap = new Map();
  const nodes = event.pathNodes.map((node, index) => {
    const role = getPropagationRole(node, index);
    const roleIndex = propagationRoleMeta.findIndex((item) => item.name === role);
    const multiplier = { 初始爆料: 0.95, 大V: 1.35, 官媒: 1.62, 普通网民: 0.62 }[role] || 1;
    const influence = Math.round(((node.symbolSize || 38) * 7200 + event.heat * 850) * multiplier);
    const arrivalIndex = Math.min(timelineData.length - 1, index * arrivalStep + (index > 2 ? 1 : 0));
    nodeArrivalMap.set(node.name, arrivalIndex);

    return {
      id: node.name,
      name: node.name,
      role,
      category: Math.max(0, roleIndex),
      value: influence,
      arrivalIndex,
      symbolSize: Math.min(76, Math.max(30, 18 + influence / 14000)),
      itemStyle: { color: propagationRoleMeta[Math.max(0, roleIndex)]?.color || '#868F9E' },
      label: { fontSize: influence > 520000 ? 14 : 12 },
    };
  });
  const links = event.pathLinks.map(([source, target], index) => {
    const sourceArrival = nodeArrivalMap.get(source) || 0;
    const targetArrival = nodeArrivalMap.get(target) || sourceArrival + 1;
    const traffic = Math.max(1200, Math.round((event.reportCount / (index + 2)) * (0.36 + event.heat / 220)));

    return {
      source,
      target,
      value: traffic,
      arrivalIndex: Math.min(timelineData.length - 1, Math.max(sourceArrival, targetArrival)),
      lineStyle: {
        width: Math.min(8, Math.max(1.6, Math.sqrt(traffic) / 26)),
        opacity: 0.42,
      },
    };
  });

  return {
    baseOption: {
      color: propagationRoleMeta.map((item) => item.color),
      tooltip: {
        trigger: 'item',
        formatter: (params) => {
          if (params.dataType === 'edge') {
            return `${params.data.source} → ${params.data.target}<br/>传播流量：${formatCount(params.data.value)}`;
          }
          return `${params.name}<br/>角色：${params.data.role}<br/>影响力：${formatCount(params.data.value)}`;
        },
      },
      legend: {
        top: 0,
        left: 8,
        icon: 'circle',
        textStyle: { color: '#444A56' },
      },
      timeline: {
        axisType: 'category',
        autoPlay: false,
        currentIndex: timelineData.length - 1,
        bottom: 0,
        left: 18,
        right: 18,
        height: 66,
        data: timelineData,
        symbol: 'circle',
        symbolSize: 8,
        checkpointStyle: {
          color: '#2A3F54',
          borderColor: '#fff',
          borderWidth: 2,
        },
        lineStyle: { color: '#DDE7EC' },
        label: { color: '#868F9E' },
        controlStyle: {
          color: '#2A3F54',
          borderColor: '#2A3F54',
        },
      },
      series: [
        {
          type: 'graph',
          layout: 'force',
          top: 56,
          right: 18,
          bottom: 92,
          left: 18,
          roam: true,
          draggable: true,
          categories: propagationRoleMeta.map((item) => ({ name: item.name, itemStyle: { color: item.color } })),
          edgeSymbol: ['none', 'arrow'],
          edgeSymbolSize: [0, 8],
          force: {
            repulsion: 360,
            edgeLength: [82, 148],
            gravity: 0.07,
            friction: 0.42,
          },
          label: {
            show: true,
            color: '#1A1F27',
            fontWeight: 850,
          },
          lineStyle: {
            color: 'source',
            curveness: 0.16,
          },
          emphasis: {
            focus: 'adjacency',
            lineStyle: { opacity: 0.88 },
          },
          animationDurationUpdate: 550,
          animationEasingUpdate: 'quinticInOut',
          data: [],
          links: [],
        },
      ],
    },
    options: timelineData.map((_time, frameIndex) => ({
      series: [
        {
          data: nodes.filter((node) => node.arrivalIndex <= frameIndex),
          links: links.filter((link) => link.arrivalIndex <= frameIndex),
        },
      ],
    })),
  };
}

function buildSankeyOption() {
  return {
    tooltip: { trigger: 'item', triggerOn: 'mousemove' },
    series: [
      {
        type: 'sankey',
        top: 14,
        right: 24,
        bottom: 18,
        left: 24,
        nodeWidth: 14,
        nodeGap: 14,
        draggable: false,
        emphasis: { focus: 'adjacency' },
        lineStyle: {
          color: 'gradient',
          curveness: 0.5,
          opacity: 0.42,
        },
        itemStyle: {
          borderColor: 'rgba(255,255,255,0.9)',
          borderWidth: 1,
        },
        label: {
          color: '#1A1F27',
          fontWeight: 760,
        },
        data: propagationSankey.nodes,
        links: propagationSankey.links,
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
  const fallbackEvent = useMemo(() => resolveFallbackEvent(id), [id]);
  const [event, setEvent] = useState(fallbackEvent);
  const [detailError, setDetailError] = useState('');

  useEffect(() => {
    let alive = true;
    setDetailError('');
    setEvent(fallbackEvent);
    api
      .getEventDetail(id)
      .then((nextEvent) => {
        if (!alive) return;
        setEvent({
          ...fallbackEvent,
          ...nextEvent,
          sentiment: nextEvent.sentiment || fallbackEvent.sentiment,
          platforms: nextEvent.platforms?.length ? nextEvent.platforms : fallbackEvent.platforms,
          trend: nextEvent.trend?.length ? nextEvent.trend : fallbackEvent.trend,
          words: nextEvent.words?.length ? nextEvent.words : fallbackEvent.words,
          keywords: nextEvent.keywords?.length ? nextEvent.keywords : fallbackEvent.keywords,
          similarEvents: nextEvent.similarEvents?.length ? nextEvent.similarEvents : fallbackEvent.similarEvents,
          pathNodes: nextEvent.pathNodes?.length ? nextEvent.pathNodes : fallbackEvent.pathNodes,
          pathLinks: nextEvent.pathLinks?.length ? nextEvent.pathLinks : fallbackEvent.pathLinks,
        });
      })
      .catch((error) => {
        if (!alive) return;
        setDetailError(error.message || '事件详情加载失败');
        setEvent(fallbackEvent);
      });
    return () => {
      alive = false;
    };
  }, [fallbackEvent, id]);
  const trendOption = useMemo(() => buildTrendOption(event), [event]);
  const sentimentOption = useMemo(() => buildPieOption(event), [event]);
  const keywordRankOption = useMemo(() => buildKeywordRankOption(event), [event]);
  const platformBarOption = useMemo(() => buildPlatformBarOption(event), [event]);
  const themeRiverOption = useMemo(() => buildThemeRiverOption(event), [event]);
  const lifecycleOption = useMemo(() => buildLifecycleOption(event), [event]);
  const sankeyOption = useMemo(() => buildSankeyOption(), []);
  const geoHeatOption = useMemo(() => buildGeoHeatOption(event), [event]);
  const traceForceOption = useMemo(() => buildTraceForceOption(event), [event]);
  const authenticityTopics = useMemo(() => buildFakeChecks(event), [event]);
  const discussionCount = Math.round(event.reportCount * (event.sentiment.negative + event.heat) * 0.18);

  const exportReport = async () => {
    const timestamp = buildTimestamp();
    const titlePart = sanitizeFilePart(event.title, '未命名事件').slice(0, 18);
    try {
      await downloadPdfFromBackend(`/api/events/${event.id}/brief.pdf`, `Trendsight-事件简报-${titlePart}-${timestamp}.pdf`);
    } catch (error) {
      console.error(error);
      window.alert(`事件简报导出失败：${error.message || '请确认后端服务已启动'}`);
    }
  };

  return (
    <AppShell>
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
              <span className={riskClass[event.risk] || 'risk-mid'}>风险 · {event.risk}</span>
              <span>
                {event.category} · {event.location}
              </span>
            </div>
            <div className="report-hero-main">
              <div>
                <h1>{event.title}</h1>
                <p>{event.summary}</p>
              </div>
              <button type="button" onClick={exportReport}>
                <Download size={18} />
                导出事件简报
              </button>
            </div>
            <div className="detail-kpi-strip">
              <KpiItem label="热度指数" value={event.heat} icon={Flame} tone="orange" />
              <KpiItem label="累计报道" value={formatCount(event.reportCount)} icon={FileCheck2} tone="blue" />
              <KpiItem label="参与讨论" value={formatCount(discussionCount)} icon={Network} tone="violet" />
              <KpiItem label="真实性置信" value={`${Math.round(event.falseConfidence * 100)}%`} icon={ShieldCheck} tone="green" />
            </div>
          </article>

          <nav className="detail-anchor-nav" aria-label="报告章节导航">
            <a href="#overview">概述</a>
            <a href="#trend">趋势</a>
            <a href="#platform">平台</a>
            <a href="#sentiment">情感</a>
            <a href="#wordcloud">词云</a>
            <a href="#keyword-rank">排行</a>
            <a href="#theme">河流图</a>
            <a href="#lifecycle">生命周期</a>
            <a href="#geo">地域</a>
            <a href="#sankey">桑基图</a>
            <a href="#trace">溯源</a>
            <a href="#authenticity">真实性</a>
            <a href="#retrieval">相似事件</a>
            <a href="#advice">建议</a>
          </nav>

          <ReportSection id="overview" label="Overview" title="事件概述">
            <div className="fact-grid">
              <FactItem label="发生时间" value={event.time} />
              <FactItem label="发生地点" value={event.location} />
              <FactItem label="直接起因" value={event.cause} />
              <FactItem label="涉事主体" value={event.people} />
            </div>
            <p className="report-paragraph">{event.summary}</p>
          </ReportSection>

          <ReportSection id="trend" label="Trend" title="报道发展趋势">
            <EChart option={trendOption} className="report-trend-chart" />
            <TrendEventAxis trend={event.trend} />
          </ReportSection>

          <ReportSection id="platform" label="Platform" title="平台数据分布">
            <EChart option={platformBarOption} className="platform-bar-chart" />
          </ReportSection>

          <section className="analysis-split">
            <ReportSection id="sentiment" label="Sentiment" title="情感分布">
              <div className="sentiment-detail-grid">
                <EChart option={sentimentOption} className="sentiment-donut-chart" />
                <SentimentBar sentiment={event.sentiment} />
              </div>
            </ReportSection>

            <ReportSection id="wordcloud" label="Word Cloud" title="关键词词云">
              <WordCloud words={event.words} getColor={getKeywordColor} />
            </ReportSection>
          </section>

          <ReportSection id="keyword-rank" label="Keyword Rank" title="关键词排行">
            <EChart option={keywordRankOption} className="keyword-rank-chart" />
          </ReportSection>

          <ReportSection id="theme" label="Theme River" title="主题演化河流图">
            <EChart option={themeRiverOption} className="theme-river-chart" />
          </ReportSection>

          <ReportSection id="lifecycle" label="Lifecycle" title="生命周期分析与预测">
            <div className="lifecycle-stage-row">
              {['潜伏期', '成长期', '高潮期', '衰退期'].map((stage) => (
                <span className={stage === event.stage ? 'active' : ''} key={stage}>
                  {stage}
                </span>
              ))}
            </div>
            <EChart option={lifecycleOption} className="lifecycle-chart" />
          </ReportSection>

          <ReportSection id="geo" label="Geo Heat" title="地理热力图">
            <EChart option={geoHeatOption} className="geo-heat-chart" />
          </ReportSection>

          <ReportSection id="sankey" label="Propagation" title="传播路径桑基图分析">
            <EChart option={sankeyOption} className="propagation-sankey-chart" />
          </ReportSection>

          <ReportSection id="trace" label="Traceability" title="事件溯源">
            <EChart option={traceForceOption} className="trace-force-chart" />
          </ReportSection>

          <ReportSection id="authenticity" label="Authenticity" title="虚假文本检测">
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
                    <b>{item.officialRatio === null ? `${item.label || '官方来源'}待接入` : `${item.label || '官方来源'} ${item.officialRatio}%`}</b>
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
            <ReportSection id="retrieval" label="Retrieval" title="历史相似事件">
              <div className="similar-list">
                {event.similarEvents.length ? (
                  event.similarEvents.map((item, index) => {
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
                  })
                ) : (
                  <p className="similar-empty">暂无相似历史事件。</p>
                )}
              </div>
            </ReportSection>

            <ReportSection id="advice" label="Advice" title="处置建议">
              {event.adviceItems?.length ? (
                <div className="advice-grid">
                  {event.adviceItems.map((item) => (
                    <article className="advice-item" key={item.label}>
                      <span>{item.label}</span>
                      <p>{item.text}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="report-paragraph">{event.advice}</p>
              )}
              <div className="keyword-list compact">
                {event.keywords.map((keyword) => (
                  <span key={keyword}>
                    <Tags size={14} />
                    {keyword}
                  </span>
                ))}
              </div>
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

function ReportSection({ id, label, title, children }) {
  return (
    <article className="report-section-card" id={id}>
      <div className="report-section-title">
        <span>{label}</span>
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

function TrendEventAxis({ trend }) {
  return (
    <div className="trend-event-axis" style={{ gridTemplateColumns: `repeat(${trend.length}, minmax(0, 1fr))` }}>
      {trend.map((item) => (
        <div className={`trend-event-slot ${item.node ? 'has-event' : ''}`} key={item.time}>
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
