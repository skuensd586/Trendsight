const HIGH_RISK_LEVELS = new Set(['高', '中高']);

const riskPriority = {
  高: 2,
  中高: 1,
};

export function isHighRiskEvent(event = {}) {
  return HIGH_RISK_LEVELS.has(event.risk);
}

export function compareRiskPriority(first = {}, second = {}) {
  const priorityDiff = (riskPriority[second.risk] || 0) - (riskPriority[first.risk] || 0);
  if (priorityDiff) return priorityDiff;
  return (second.heat || 0) - (first.heat || 0);
}
