import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, DatabaseZap, Search, TrendingUp } from 'lucide-react';
import AppShell from '../components/AppShell.jsx';
import EventCard from '../components/EventCard.jsx';
import { api } from '../api/index.js';

const PAGE_SIZE = 7;

const sortOptions = [
  { value: 'heat', label: '按热度' },
  { value: 'time', label: '按时间' },
  { value: 'negative', label: '按负面' },
];

const riskOptions = [
  { value: 'all', label: '全部' },
  { value: 'high', label: '高' },
  { value: 'mid_high', label: '中高' },
  { value: 'mid', label: '中' },
  { value: 'low', label: '低' },
];

const timeOptions = [
  { value: 'today', label: '今日' },
  { value: '7d', label: '近 7 天' },
  { value: '30d', label: '近 30 天' },
];

export default function DashboardPage() {
  const [sortBy, setSortBy] = useState('heat');
  const [riskFilter, setRiskFilter] = useState('all');
  const [timeFilter, setTimeFilter] = useState('7d');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [eventItems, setEventItems] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, page_size: PAGE_SIZE, total: 0, total_pages: 1 });
  const [sourceStatus, setSourceStatus] = useState({ normal: 0, limited: 0, total: 0 });
  const [dashboardError, setDashboardError] = useState('');

  const metrics = useMemo(() => {
    const highRiskCount = eventItems.filter((event) => ['高', '中高'].includes(event.risk)).length;
    return [
      {
        title: '实时监测事件',
        value: pagination.total ? pagination.total * 32 : 0,
        note: '今日新增 23',
        delta: '+23',
        icon: TrendingUp,
        tone: 'green',
      },
      {
        title: '高风险预警',
        value: highRiskCount,
        note: '需优先处置',
        delta: `+${highRiskCount}`,
        icon: AlertTriangle,
        tone: 'red',
      },
      {
        title: '接入采集源',
        value: sourceStatus.total,
        note: `${sourceStatus.normal} 正常 · ${sourceStatus.limited} 限流`,
        delta: '正常',
        icon: DatabaseZap,
        tone: 'blue',
      },
    ];
  }, [eventItems, pagination.total, sourceStatus]);

  useEffect(() => {
    setPage(1);
  }, [query, riskFilter, sortBy, timeFilter]);

  useEffect(() => {
    let alive = true;
    setDashboardError('');
    api
      .getHotEvents({
        q: query.trim(),
        risk_level: riskFilter === 'all' ? undefined : riskFilter,
        time_range: timeFilter,
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
  }, [query, riskFilter, sortBy, timeFilter, page]);

  useEffect(() => {
    let alive = true;
    api
      .getUserProfile()
      .then((profile) => {
        if (!alive) return;
        const sources = profile.preferences?.platform_urls || [];
        const limited = sources.filter((source) => ['限流', 'limited', 'error'].includes(source.status)).length;
        setSourceStatus({
          total: sources.length,
          normal: sources.length - limited,
          limited,
        });
      })
      .catch(() => {
        if (!alive) return;
        setSourceStatus({ normal: 0, limited: 0, total: 0 });
      });
    return () => {
      alive = false;
    };
  }, []);

  const totalPages = Math.max(1, pagination.total_pages || Math.ceil((pagination.total || eventItems.length) / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const visibleEvents = eventItems;

  const insight = useMemo(() => {
    const highRiskEvents = [...eventItems].filter((event) => ['高', '中高'].includes(event.risk)).sort((a, b) => b.heat - a.heat);
    const keywordRank = eventItems
      .flatMap((event) => event.keywords)
      .reduce((acc, keyword) => {
        acc[keyword] = (acc[keyword] || 0) + 1;
        return acc;
      }, {});
    const hotKeywords = Object.entries(keywordRank)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([keyword]) => keyword);
    return {
      highRiskEvents: highRiskEvents.slice(0, 3),
      hotKeywords,
      normalSources: sourceStatus.normal,
      limitedSources: sourceStatus.limited,
    };
  }, [eventItems, sourceStatus]);

  return (
    <AppShell wide>
      <section className="ops-dashboard-header">
        <div>
          <h1>舆情事件看板</h1>
          <p>实时聚合全网热点事件，辅助分析师快速研判</p>
        </div>
        <label className="dashboard-search">
          <Search size={18} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索事件 / 关键词" />
        </label>
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

        <div className="segmented-group">
          <span>时间</span>
          {timeOptions.map((option) => (
            <button
              className={timeFilter === option.value ? 'active' : ''}
              onClick={() => setTimeFilter(option.value)}
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
          <InsightBlock title="高风险待处理">
            {insight.highRiskEvents.map((event) => (
              <Link to={`/events/${event.id}`} className="insight-event" key={event.id}>
                <span>{event.title}</span>
                <b>热度 {event.heat}</b>
              </Link>
            ))}
          </InsightBlock>

          <InsightBlock title="今日高频关键词">
            <div className="insight-keywords">
              {insight.hotKeywords.map((keyword) => (
                <span key={keyword}>{keyword}</span>
              ))}
            </div>
          </InsightBlock>

          <InsightBlock title="采集源状态">
            <div className="source-health">
              <p>
                <span className="ok-dot" />
                正常运行
                <b>{insight.normalSources}</b>
              </p>
              <p>
                <span className="warn-dot" />
                限流关注
                <b>{insight.limitedSources}</b>
              </p>
            </div>
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
