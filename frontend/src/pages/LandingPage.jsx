import { Link } from 'react-router-dom';
import { BellRing, Bot, ChartNoAxesCombined, DatabaseZap, Radar } from 'lucide-react';

const features = [
  {
    title: '多平台监测',
    desc: '把新闻、社交平台和论坛内容按事件归集，方便统一查看。',
    icon: DatabaseZap,
  },
  {
    title: '风险预警',
    desc: '按热度、负面占比和可信度标出需要优先处理的事件。',
    icon: BellRing,
  },
  {
    title: '趋势分析',
    desc: '查看报道量、平台来源和情绪变化，判断事件走势。',
    icon: ChartNoAxesCombined,
  },
  {
    title: '事件问答',
    desc: '围绕当前事件追问起因、风险和处置建议。',
    icon: Bot,
  },
];

export default function LandingPage() {
  return (
    <main className="landing-page">
      <header className="landing-nav">
        <div className="brand-mark">
          <span className="brand-symbol">
            <Radar size={20} strokeWidth={2.4} />
          </span>
          <span>Trendsight</span>
        </div>
        <div className="landing-actions">
          <Link to="/login" className="ghost-link">
            登录
          </Link>
          <Link to="/register" className="solid-link">
              创建账号
          </Link>
        </div>
      </header>

      <section className="hero">
        <div className="hero-scene" aria-hidden="true">
          <span className="signal-node node-a" />
          <span className="signal-node node-b" />
          <span className="signal-node node-c" />
          <span className="signal-node node-d" />
          <div className="radar-card">
            <div className="radar-rings">
              <span />
              <span />
              <span />
              <i />
            </div>
            <div className="signal-list">
              <b>当前热点</b>
              <span>热度 94</span>
              <span>风险 高</span>
              <span>负面 24%</span>
            </div>
          </div>
        </div>
        <div className="hero-copy">
          <h1>Trendsight</h1>
          <p>
            用于监测突发公共事件和社会热点。你可以先看高风险事件，再查看传播、情绪、可信度和处置建议。
          </p>
          <div className="hero-actions">
            <Link to="/login" className="primary-cta">
              进入看板
            </Link>
            <Link to="/register" className="secondary-cta">
              创建账号
            </Link>
          </div>
        </div>
      </section>

      <section className="feature-grid" aria-label="主要功能">
        {features.map((feature) => {
          const Icon = feature.icon;
          return (
            <article className="feature-card" key={feature.title}>
              <div className="feature-image">
                <Icon size={42} strokeWidth={1.8} />
              </div>
              <h2>{feature.title}</h2>
              <p>{feature.desc}</p>
            </article>
          );
        })}
      </section>
    </main>
  );
}
