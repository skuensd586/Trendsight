import { Clock3, FileText, Flame, MessageCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import SentimentBar from './SentimentBar.jsx';
import { isHighRiskEvent } from '../utils/risk.js';

const riskClass = {
  高: 'risk-high',
  中高: 'risk-mid-high',
  中: 'risk-mid',
  低: 'risk-low',
};

const stageClass = {
  高潮期: 'stage-peak',
  成长期: 'stage-growth',
  衰退期: 'stage-decline',
  潜伏期: 'stage-latent',
};

function formatCount(value) {
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`;
  return value.toLocaleString();
}

export default function EventCard({ event, index = 0 }) {
  const navigate = useNavigate();
  const discussionCount = Math.round(event.reportCount * (event.sentiment.negative + event.heat) * 0.18);
  const isAlert = isHighRiskEvent(event) || event.sentiment.negative >= 40;
  const category = event.category && event.category !== '未分类' ? event.category : '';
  const location = event.location && !['未标注地区', '未对应地区'].includes(event.location) ? event.location : '';
  const contextTag = [category, location].filter(Boolean).join(' · ');
  const openDetail = () => {
    if (!event.id) return;
    navigate(`/events/${encodeURIComponent(event.id)}`);
  };

  return (
    <article
      className={`event-row-card ${isAlert ? 'is-alert' : ''}`}
      onClick={openDetail}
      onKeyDown={(eventKey) => {
        if (eventKey.key === 'Enter') openDetail();
      }}
      role="button"
      tabIndex={0}
    >
      <div className="event-rank">{String(index + 1).padStart(2, '0')}</div>

      <section className="event-row-main">
        <div className="event-row-tags">
          <span className={stageClass[event.stage] || 'stage-growth'}>{event.stage}</span>
          <span className={riskClass[event.risk] || 'risk-mid'}>风险 {event.risk}</span>
          {contextTag ? <span>{contextTag}</span> : null}
        </div>
        <h3>{event.title}</h3>
        <div className="event-row-meta">
          <span>
            <Clock3 size={13} />
            {event.time}
          </span>
          <i aria-hidden="true">·</i>
          <span>
            <FileText size={13} />
            <b>{formatCount(event.reportCount)}</b> 条报道
          </span>
          <i aria-hidden="true">·</i>
          <span>
            <MessageCircle size={13} />
            <b>{formatCount(discussionCount)}</b> 条讨论
          </span>
        </div>
      </section>

      <section className="event-row-sentiment">
        <p>负面情绪 {event.sentiment.negative}%</p>
        <SentimentBar sentiment={event.sentiment} dense />
      </section>

      <section className="event-row-heat">
        <span>热度</span>
        <strong>{event.heat.toLocaleString()}</strong>
        <p>
          <Flame size={14} />
          +{Math.max(12, event.sentiment.negative + event.heat - 70)}%
        </p>
      </section>

    </article>
  );
}
