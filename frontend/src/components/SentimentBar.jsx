export default function SentimentBar({ sentiment, dense = false }) {
  return (
    <div className={`sentiment-bar-wrap ${dense ? 'dense' : ''}`}>
      <div className="sentiment-bar" aria-label="情感倾向分段条">
        <span className="positive" style={{ width: `${sentiment.positive}%` }} />
        <span className="neutral" style={{ width: `${sentiment.neutral}%` }} />
        <span className="negative" style={{ width: `${sentiment.negative}%` }} />
      </div>
      <div className="sentiment-bar-values">
        <span className="positive">正 {sentiment.positive}%</span>
        <span className="neutral">中 {sentiment.neutral}%</span>
        <span className="negative">负 {sentiment.negative}%</span>
      </div>
    </div>
  );
}
