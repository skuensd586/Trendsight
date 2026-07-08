import { useMemo } from 'react';

const VIEWBOX_WIDTH = 640;
const VIEWBOX_HEIGHT = 340;
const CLOUD_PADDING = 24;
const MIN_FONT_SIZE = 22;
const MAX_FONT_SIZE = 58;

function estimateTextWidth(text, fontSize) {
  return Array.from(text).reduce((width, char) => {
    const code = char.codePointAt(0);
    return width + fontSize * (code > 255 ? 0.92 : 0.56);
  }, 0);
}

function overlaps(first, second) {
  return (
    first.left < second.right &&
    first.right > second.left &&
    first.top < second.bottom &&
    first.bottom > second.top
  );
}

function createBox(x, y, width, height) {
  return {
    left: x - width / 2,
    right: x + width / 2,
    top: y - height / 2,
    bottom: y + height / 2,
  };
}

function isInside(box) {
  return (
    box.left >= CLOUD_PADDING &&
    box.right <= VIEWBOX_WIDTH - CLOUD_PADDING &&
    box.top >= CLOUD_PADDING &&
    box.bottom <= VIEWBOX_HEIGHT - CLOUD_PADDING
  );
}

function buildLayout(words, getColor) {
  const normalized = words
    .map(([name, value], index) => ({ name, value: Number(value) || 0, index }))
    .filter((word) => word.name && word.value > 0)
    .sort((first, second) => second.value - first.value);

  if (!normalized.length) return [];

  const values = normalized.map((word) => word.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const placed = [];

  return normalized.map((word, index) => {
    const ratio = (word.value - min) / span;
    const fontSize = Math.round(MIN_FONT_SIZE + Math.sqrt(ratio) * (MAX_FONT_SIZE - MIN_FONT_SIZE));
    const width = estimateTextWidth(word.name, fontSize) + 16;
    const height = fontSize * 1.1;
    const centerX = VIEWBOX_WIDTH / 2;
    const centerY = VIEWBOX_HEIGHT / 2;
    let best = null;

    for (let step = 0; step < 900; step += 1) {
      const angle = step * 0.48 + index * 0.72;
      const radius = step === 0 ? 0 : 4.2 * Math.sqrt(step) + index * 4;
      const x = centerX + Math.cos(angle) * radius;
      const y = centerY + Math.sin(angle) * radius * 0.64;
      const box = createBox(x, y, width, height);

      if (isInside(box) && !placed.some((item) => overlaps(item.box, box))) {
        best = { x, y, box };
        break;
      }
    }

    if (!best) {
      const columns = 3;
      const fallbackX = CLOUD_PADDING + 90 + (index % columns) * 210;
      const fallbackY = CLOUD_PADDING + 48 + Math.floor(index / columns) * 78;
      best = { x: fallbackX, y: fallbackY, box: createBox(fallbackX, fallbackY, width, height) };
    }

    placed.push({ box: best.box });

    return {
      ...word,
      x: Math.round(best.x),
      y: Math.round(best.y),
      fontSize,
      color: getColor?.(word.name, word.value, index) || '#366FB8',
    };
  });
}

export default function WordCloud({ words = [], getColor, className = '' }) {
  const layout = useMemo(() => buildLayout(words, getColor), [words, getColor]);
  const ariaLabel = layout.map((word) => `${word.name} ${word.value}`).join('，');

  return (
    <div className={`word-cloud-panel ${className}`} role="img" aria-label={`关键词词云：${ariaLabel}`}>
      <svg className="word-cloud-svg" viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`} aria-hidden="true">
        {layout.map((word, index) => (
          <g className="word-cloud-token" key={`${word.name}-${word.index}`}>
            <title>{`${word.name}：权重 ${word.value}`}</title>
            <text
              x={word.x}
              y={word.y}
              fill={word.color}
              fontSize={word.fontSize}
              textAnchor="middle"
              dominantBaseline="central"
              className={`word-cloud-token-${index}`}
            >
              {word.name}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
