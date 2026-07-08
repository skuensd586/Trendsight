import { Link } from 'react-router-dom';
import { BellRing, Bot, ChartNoAxesCombined, DatabaseZap, Radar } from 'lucide-react';

const features = [
  {
    title: '多源采集',
    desc: '接入新闻、社交平台与论坛社区，形成统一事件数据池。',
    icon: DatabaseZap,
  },
  {
    title: '风险预警',
    desc: '结合热度、情绪与真实性置信度，识别高风险舆情。',
    icon: BellRing,
  },
  {
    title: '趋势分析',
    desc: '用 ECharts 展示传播趋势、平台占比和情感分布。',
    icon: ChartNoAxesCombined,
  },
  {
    title: '智能问答',
    desc: '围绕当前事件进行摘要、追问和辅助研判。',
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
            注册
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
              <b>实时热点</b>
              <span>热度 94</span>
              <span>风险 高</span>
              <span>负面 24%</span>
            </div>
          </div>
        </div>
        <div className="hero-copy">
          <p className="eyebrow">Network Public Opinion Intelligence</p>
          <h1>Trendsight</h1>
          <p>
            面向突发公共事件与社会热点话题的网络舆情事件智能分析系统，帮助快速发现热点、识别风险、追踪传播并生成分析报告。
          </p>
          <div className="hero-actions">
            <Link to="/login" className="primary-cta">
              进入系统
            </Link>
            <Link to="/register" className="secondary-cta">
              创建账号
            </Link>
          </div>
        </div>
      </section>

      <section className="feature-grid" aria-label="系统功能介绍">
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
