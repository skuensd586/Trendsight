import { useEffect, useMemo, useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { Bell, CircleUserRound, Download, LayoutDashboard, MessageSquareText, Radar } from 'lucide-react';
import { api } from '../api/index.js';
import { events } from '../data/events.js';

export default function AppShell({ children, wide = false }) {
  const navigate = useNavigate();
  const user = localStorage.getItem('trendsight-user') || 'analyst';
  const fallbackTopEvents = useMemo(() => [...events].sort((first, second) => second.heat - first.heat).slice(0, 5), []);
  const [topEvents, setTopEvents] = useState(fallbackTopEvents);
  const highRiskCount = topEvents.filter((event) => ['高', '中高'].includes(event.risk)).length;

  useEffect(() => {
    let alive = true;
    api
      .getHotEvents({ sort: 'heat', page: 1, page_size: 5 })
      .then((result) => {
        if (!alive) return;
        setTopEvents(result.items?.length ? result.items : fallbackTopEvents);
      })
      .catch(() => {
        if (!alive) return;
        setTopEvents(fallbackTopEvents);
      });
    return () => {
      alive = false;
    };
  }, [fallbackTopEvents]);

  const exportBrief = () => {
    const briefEvents = topEvents
      .map((event, index) => `${index + 1}. ${event.title}｜热度 ${event.heat}｜风险 ${event.risk}`)
      .join('\n');
    const content = [`Trendsight 舆情简报`, `高风险预警：${highRiskCount} 条`, `重点事件：`, briefEvents].join('\n');
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'Trendsight-舆情简报.txt';
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand-mark" to="/dashboard">
          <span className="brand-symbol">
            <Radar size={20} strokeWidth={2.4} />
          </span>
          <span>Trendsight</span>
        </Link>

        <nav className="topbar-nav">
          <NavLink to="/dashboard">
            <LayoutDashboard size={17} />
            舆情看板
          </NavLink>
          <NavLink to="/qa">
            <MessageSquareText size={17} />
            智能问答
          </NavLink>
        </nav>

        <div className="topbar-actions">
          <button className="topbar-icon-action alert-action" aria-label={`高风险预警 ${highRiskCount} 条`} type="button">
            <Bell size={17} />
            <span />
          </button>
          <button className="topbar-export-action" onClick={exportBrief} type="button">
            <Download size={17} />
            导出简报
          </button>
          <button className="profile-entry" onClick={() => navigate('/profile')} type="button">
            <CircleUserRound size={18} />
            <span>{user}</span>
          </button>
        </div>
      </header>
      <main className={`shell-main ${wide ? 'wide-shell-main' : ''}`}>{children}</main>
    </div>
  );
}
