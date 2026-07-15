import { useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { Bell, CircleUserRound, LayoutDashboard, MessageSquareText, Radar } from 'lucide-react';

export default function AppShell({ children, wide = false, topbarAction = null }) {
  const navigate = useNavigate();
  const user = localStorage.getItem('trendsight-user') || 'analyst';
  const profileEntryLabel = `${user} 的个人中心`;
  const [alertsOpen, setAlertsOpen] = useState(false);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <Link className="brand-mark" to="/dashboard">
            <span className="brand-symbol">
              <Radar size={20} strokeWidth={2.4} />
            </span>
            <span>Trendsight</span>
          </Link>

          <nav className="topbar-nav">
            <NavLink to="/dashboard">
              <LayoutDashboard size={17} />
              事件看板
            </NavLink>
            <NavLink to="/qa">
              <MessageSquareText size={17} />
              事件问答
            </NavLink>
          </nav>

          <div className="topbar-actions">
            {topbarAction}
            <button
              aria-expanded={alertsOpen}
              aria-haspopup="dialog"
              aria-label="预警通知"
              className="topbar-icon-action alert-action"
              onClick={() => setAlertsOpen((value) => !value)}
              title="预警通知"
              type="button"
            >
              <Bell size={17} />
              <span />
            </button>
            {alertsOpen ? (
              <div className="alert-popover" role="dialog" aria-label="预警通知">
                <strong>预警通知</strong>
                <p>当前没有新的预警</p>
                <button
                  type="button"
                  onClick={() => {
                    setAlertsOpen(false);
                    navigate('/dashboard');
                  }}
                >
                  查看高风险事件
                </button>
              </div>
            ) : null}
            <button className="profile-entry" onClick={() => navigate('/profile')} type="button">
              <CircleUserRound size={18} />
              <span>{profileEntryLabel}</span>
            </button>
          </div>
        </div>
      </header>
      <main className={`shell-main ${wide ? 'wide-shell-main' : ''}`}>{children}</main>
    </div>
  );
}
