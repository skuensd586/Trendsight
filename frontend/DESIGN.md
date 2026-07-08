# Design

## Design Intent

Trendsight uses a restrained product UI language for a mature public-opinion intelligence platform. The interface should feel operational, trustworthy, and calm. The design serves fast analysis rather than brand spectacle.

## Theme

Light product theme using a low-saturation Chinese palette:

- Brand primary / navigation / primary action: Qingdai `#2A3F54`
- Page background: Yuebai `#F7F9FB`
- Regular card surface: Ivory white `#FCFCFD`
- Main text: Xuanhei `#1A1F27`
- Secondary text: Huimo `#444A56`
- Helper text: soft gray `#868F9E`
- Borders and dividers: Yanqing `#E2E7EF`
- Positive / trusted / low risk: Zhuqing `#3A9477`
- Neutral / information / regular event: Jilan `#366FB8`
- Negative / high risk / false-content warning: Yanzhi `#C83C3C`
- Heat / growth / review warning: Zheshi `#D4783A`
- AI / trace path nodes: Ziwan `#7962B3`

Glass treatment is restrained: use translucent white, light blur, and soft shadows only on high-level KPI cards, sticky navigation/search, and selected analysis modules such as traceability and authenticity. Event lists, text-heavy report sections, and forms stay mostly solid for readability.

## Typography

Use one system sans stack across the product:

```css
Inter, "Microsoft YaHei", "PingFang SC", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif
```

Product screens should use a tight hierarchy:

- Page title: 30-38px desktop, smaller on mobile
- Report title: 28-36px
- Section title: 20-22px
- Card metric: 26-32px
- Body: 16px
- Labels and metadata: 12-14px

Avoid hero-scale typography inside authenticated pages.

## Layout

- Authenticated pages use a top navigation bar and centered content width.
- Dashboard uses a workbench layout: KPI summary, filter toolbar, event list, and a right insight rail.
- Event detail uses a report column plus a sticky intelligent Q&A panel.
- Profile uses a configuration console layout with account summary, preferences, and grouped source settings.
- Mobile collapses to one column with secondary panels below primary content.

## Components

### Navigation

Top bar is sticky and lightly glassed. Active navigation uses a subtle Jilan tint and Qingdai text.

### Buttons

Primary buttons use Qingdai with white text. Secondary buttons use white or pale Yuebai surfaces with visible Yanqing borders. Buttons should not use bright blue unless representing selected or informational state.

### Cards and Panels

Cards use restrained radius, light borders, and subtle Qingdai-tinted shadows. KPI cards and selected analytical modules may use glass treatment; dense event rows and text-heavy cards remain solid Ivory white.

### Tags and Chips

Chips use semantic tinting:

- Risk high: Yanzhi tint
- Risk medium or growth: Zheshi tint
- Status normal and positive sentiment: Zhuqing tint
- Neutral metadata and regular information: Jilan or Yanqing tint

### Charts

Charts prioritize legibility. Use Jilan line charts for trend, Zhuqing/Jilan/Yanzhi segmented bars for sentiment comparison, donut charts only when proportions matter, and a restrained rose chart for platform distribution.

### Forms

Inputs are labeled, 44px or taller, with visible borders and enough contrast. Placeholders are helper text, not labels.

## Motion

Use only micro-interactions:

- Hover/focus elevation on clickable event rows
- Button press feedback
- 150-250ms transitions

No decorative page-load choreography. Respect `prefers-reduced-motion`.

## Quality Bar

Before delivery, verify:

- Desktop and mobile screenshots for landing, dashboard, event detail, Q&A, and profile.
- No horizontal scroll on small screens.
- No text collision or chart blank states.
- Build passes.
- Dependency audit reports no moderate or higher vulnerabilities.
