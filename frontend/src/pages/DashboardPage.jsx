import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, DatabaseZap, FileDown, Search, TrendingUp } from 'lucide-react';
import AppShell from '../components/AppShell.jsx';
import EventCard from '../components/EventCard.jsx';
import { api } from '../api/index.js';
import { buildTimestamp, downloadPdfFromBackend, toQuery } from '../utils/briefExport.js';
import { compareRiskPriority, isHighRiskEvent } from '../utils/risk.js';

const PAGE_SIZE = 7;

const sortOptions = [
  { value: 'heat', label: '热度优先' },
  { value: 'time', label: '最新优先' },
  { value: 'negative', label: '负面优先' },
];

const riskOptions = [
  { value: 'all', label: '全部' },
  { value: 'high', label: '高' },
  { value: 'mid_high', label: '中高' },
  { value: 'mid', label: '中' },
  { value: 'low', label: '低' },
];

const limitedSourceStatuses = new Set(['限流', 'limited', 'error']);

function normalizeSource(source = {}, index = 0) {
  const status = limitedSourceStatuses.has(source.status) ? '限流' : '正常';
  return {
    name: source.name || source.platform_name || `监测源 ${index + 1}`,
    url: source.url || '',
    frequency: source.frequency || (source.frequency_minutes ? `${source.frequency_minutes} 分钟` : '未设置更新频率'),
    status,
  };
}

function compactSourceUrl(url = '') {
  const text = String(url).trim();
  if (!text || text === 'https://') return '未配置网址';
  return text.replace(/^https?:\/\//, '').replace(/\/$/, '');
}

export default function DashboardPage() {
  const [sortBy, setSortBy] = useState('heat');
  const [riskFilter, setRiskFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [eventItems, setEventItems] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, page_size: PAGE_SIZE, total: 0, total_pages: 1 });
  const [sourceStatus, setSourceStatus] = useState({ normal: 0, limited: 0, total: 0, sources: [] });
  const [dashboardError, setDashboardError] = useState('');

  const highRiskEvents = useMemo(() => [...eventItems].filter(isHighRiskEvent).sort(compareRiskPriority), [eventItems]);
  const highRiskCount = highRiskEvents.length;

  const metrics = useMemo(() => {
    return [
      {
        title: '监测到的事件',
        value: pagination.total ? pagination.total * 32 : 0,
        note: '今日新增 23 条',
        delta: '+23',
        icon: TrendingUp,
        tone: 'green',
      },
      {
        title: '需优先处理',
        value: highRiskCount,
        note: '当前列表',
        delta: '优先看',
        icon: AlertTriangle,
        tone: 'red',
      },
      {
        title: '接入监测源',
        value: sourceStatus.total,
        note: `${sourceStatus.normal} 正常 · ${sourceStatus.limited} 限流`,
        delta: '运行中',
        icon: DatabaseZap,
        tone: 'blue',
      },
    ];
  }, [highRiskCount, pagination.total, sourceStatus]);

  useEffect(() => {
    setPage(1);
  }, [query, riskFilter, sortBy]);

  useEffect(() => {
    let alive = true;
    setDashboardError('');
    api
      .getHotEvents({
        q: query.trim(),
        risk_level: riskFilter === 'all' ? undefined : riskFilter,
        sort: sortBy,
        page,
        page_size: PAGE_SIZE,
      })
      .then((result) => {
        if (!alive) return;
        setEventItems(result.items || []);
        setPagination(result.pagination || { page, page_size: PAGE_SIZE, total: result.items?.length || 0, total_pages: 1 });
      })
      .catch((error) => {
        if (!alive) return;
        setDashboardError(error.message || '事件列表加载失败');
        setEventItems([]);
        setPagination({ page: 1, page_size: PAGE_SIZE, total: 0, total_pages: 1 });
      });
    return () => {
      alive = false;
    };
  }, [query, riskFilter, sortBy, page]);

  useEffect(() => {
    let alive = true;
    api
      .getUserProfile()
      .then((profile) => {
        if (!alive) return;
        const sources = (profile.preferences?.platform_urls || []).map(normalizeSource);
        const limited = sources.filter((source) => source.status === '限流').length;
        setSourceStatus({
          total: sources.length,
          normal: sources.length - limited,
          limited,
          sources,
        });
      })
      .catch(() => {
        if (!alive) return;
        setSourceStatus({ normal: 0, limited: 0, total: 0, sources: [] });
      });
    return () => {
      alive = false;
    };
  }, []);

  const totalPages = Math.max(1, pagination.total_pages || Math.ceil((pagination.total || eventItems.length) / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const visibleEvents = eventItems;

  const insight = useMemo(() => {
    return {
      highRiskEvents: highRiskEvents.slice(0, 3),
      normalSources: sourceStatus.normal,
      limitedSources: sourceStatus.limited,
      sources: sourceStatus.sources.slice(0, 4),
      hiddenSourceCount: Math.max(0, sourceStatus.sources.length - 4),
    };
  }, [highRiskEvents, sourceStatus]);

  const exportDashboardBrief = async () => {
    const timestamp = buildTimestamp();
    const params = toQuery({
      q: query.trim(),
      risk_level: riskFilter === 'all' ? undefined : riskFilter,
      sort: sortBy,
      page,
      size: PAGE_SIZE,
    });
    try {
      await downloadPdfFromBackend(`/api/events/brief/dashboard.pdf${params}`, `Trendsight-事件看板简报-${timestamp}.pdf`);
    } catch (error) {
      console.error(error);
      window.alert(`导出看板简报失败：${error.message || '请确认数据服务可用'}`);
    }
  };

  return (
    <AppShell
      wide
      topbarAction={
        <button className="topbar-export-action" type="button" onClick={exportDashboardBrief}>
          <FileDown size={17} />
          导出看板简报
        </button>
      }
    >
      <section className="ops-dashboard-header">
        <div>
          <h1>舆情事件看板</h1>
        </div>
        <div className="dashboard-header-actions">
          <label className="dashboard-search">
            <Search size={18} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索事件或关键词" />
          </label>
        </div>
      </section>

      <section className="metric-overview">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <article className="overview-metric" key={metric.title}>
              <div>
                <span>{metric.title}</span>
                <strong>{metric.value}</strong>
                <p>{metric.note}</p>
              </div>
              <em className={metric.tone}>
                <Icon size={0} />
                {metric.delta}
              </em>
            </article>
          );
        })}
      </section>

      <section className="event-toolbar">
        <div className="segmented-group">
          <span>排序</span>
          {sortOptions.map((option) => (
            <button className={sortBy === option.value ? 'active' : ''} onClick={() => setSortBy(option.value)} key={option.value} type="button">
              {option.label}
            </button>
          ))}
        </div>

        <div className="segmented-group">
          <span>风险</span>
          {riskOptions.map((option) => (
            <button
              className={riskFilter === option.value ? 'active' : ''}
              onClick={() => setRiskFilter(option.value)}
              key={option.value}
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>

        <p>{dashboardError || `共 ${pagination.total || eventItems.length} 条事件`}</p>
      </section>

      <section className="dashboard-workbench">
        <div className="event-list-panel">
          <div className="event-row-list">
            {visibleEvents.map((event, index) => (
              <EventCard event={event} index={(currentPage - 1) * PAGE_SIZE + index} key={event.id} />
            ))}
          </div>

          <div className="pagination-toolbar" aria-label="事件列表分页">
            <button type="button" onClick={() => setPage(1)} disabled={currentPage === 1}>
              <ChevronsLeft size={16} />
              首页
            </button>
            <button type="button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={currentPage === 1}>
              <ChevronLeft size={16} />
              上一页
            </button>
            <span>
              第 {currentPage} / {totalPages} 页
            </span>
            <button type="button" onClick={() => setPage((value) => Math.min(totalPages, value + 1))} disabled={currentPage === totalPages}>
              下一页
              <ChevronRight size={16} />
            </button>
            <button type="button" onClick={() => setPage(totalPages)} disabled={currentPage === totalPages}>
              尾页
              <ChevronsRight size={16} />
            </button>
          </div>
        </div>

        <aside className="insight-rail">
          <InsightBlock title="优先查看">
            {insight.highRiskEvents.map((event) => (
              <Link to={`/events/${event.id}`} className="insight-event" key={event.id}>
                <span>{event.title}</span>
                <b>热度 {event.heat}</b>
              </Link>
            ))}
          </InsightBlock>

          <InsightBlock title="监测源状态">
            <div className="source-health">
              <p>
                <span className="ok-dot" />
                运行正常
                <b>{insight.normalSources}</b>
              </p>
              <p>
                <span className="warn-dot" />
                限流或异常
                <b>{insight.limitedSources}</b>
              </p>
            </div>
            {insight.sources.length ? (
              <div className="source-mini-list">
                {insight.sources.map((source, index) => (
                  <div className="source-mini-item" key={`${source.name}-${source.url}-${index}`}>
                    <span className={source.status === '限流' ? 'warn-dot' : 'ok-dot'} />
                    <div>
                      <strong>{source.name}</strong>
                      <small>{compactSourceUrl(source.url)}</small>
                    </div>
                    <em>{source.frequency}</em>
                  </div>
                ))}
                {insight.hiddenSourceCount ? <p className="source-mini-more">另有 {insight.hiddenSourceCount} 个监测源</p> : null}
              </div>
            ) : (
              <p className="source-mini-empty">还没有配置监测源</p>
            )}
          </InsightBlock>

        </aside>
      </section>
    </AppShell>
  );
}

function InsightBlock({ title, children }) {
  return (
    <article className="insight-block">
      <h2>{title}</h2>
      {children}
    </article>
  );
}
