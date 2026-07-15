const totalFigures = 20;

export default function SentimentCrowd({ sentiment }) {
  const positiveCount = Math.round((sentiment.positive / 100) * totalFigures);
  const neutralCount = Math.round((sentiment.neutral / 100) * totalFigures);
  const figures = Array.from({ length: totalFigures }, (_, index) => {
    if (index < positiveCount) return 'positive';
    if (index < positiveCount + neutralCount) return 'neutral';
    return 'negative';
  });

  return (
    <div className="sentiment-panel">
      <div className="people-grid" aria-label="情绪占比图">
        {figures.map((type, index) => (
          <span className={`person ${type}`} key={`${type}-${index}`}>
            <i />
          </span>
        ))}
      </div>
      <div className="sentiment-values">
        <span className="positive">正向 {sentiment.positive}%</span>
        <span className="neutral">中性 {sentiment.neutral}%</span>
        <span className="negative">负向 {sentiment.negative}%</span>
      </div>
    </div>
  );
}
