export default function SentimentBar({ sentiment, dense = false }) {
  const description = `情绪占比：正向 ${sentiment.positive}%，中性 ${sentiment.neutral}%，负向 ${sentiment.negative}%`;

  return (
    <div className={`sentiment-bar-wrap ${dense ? 'dense' : ''}`}>
      <div className="sentiment-bar" aria-label={description}>
        <span className="positive" style={{ width: `${sentiment.positive}%` }} />
        <span className="neutral" style={{ width: `${sentiment.neutral}%` }} />
        <span className="negative" style={{ width: `${sentiment.negative}%` }} />
      </div>
      <div className="sentiment-bar-values">
        <span className="positive">正向 {sentiment.positive}%</span>
        <span className="neutral">中性 {sentiment.neutral}%</span>
        <span className="negative">负向 {sentiment.negative}%</span>
      </div>
    </div>
  );
}
