from __future__ import annotations

import base64
import binascii
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image as RLImage
from reportlab.platypus import KeepTogether
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


FONT_NAME = "Helvetica"
MAX_CHART_BYTES = 6 * 1024 * 1024
REGISTERED_FONT_NAME: str | None = None


def _register_chinese_font() -> str:
    global REGISTERED_FONT_NAME

    if REGISTERED_FONT_NAME:
        return REGISTERED_FONT_NAME

    candidates = [
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
        Path("C:/Windows/Fonts/Deng.ttf"),
    ]
    for path in candidates:
        if path.exists():
            font_name = "TrendsightCN"
            if font_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(font_name, str(path)))
            REGISTERED_FONT_NAME = font_name
            return REGISTERED_FONT_NAME

    REGISTERED_FONT_NAME = FONT_NAME
    return REGISTERED_FONT_NAME


def _styles():
    font = _register_chinese_font()
    base = getSampleStyleSheet()
    base.add(
        ParagraphStyle(
            name="BriefTitle",
            parent=base["Title"],
            fontName=font,
            fontSize=22,
            leading=30,
            textColor=colors.HexColor("#152238"),
            alignment=TA_CENTER,
            spaceAfter=8,
        )
    )
    base.add(
        ParagraphStyle(
            name="BriefSubtitle",
            parent=base["BodyText"],
            fontName=font,
            fontSize=11,
            leading=18,
            textColor=colors.HexColor("#2f3a4a"),
            alignment=TA_CENTER,
            spaceAfter=14,
        )
    )
    base.add(
        ParagraphStyle(
            name="BriefHeading",
            parent=base["Heading2"],
            fontName=font,
            fontSize=14,
            leading=20,
            textColor=colors.HexColor("#18345d"),
            spaceBefore=12,
            spaceAfter=8,
        )
    )
    base.add(
        ParagraphStyle(
            name="BriefBody",
            parent=base["BodyText"],
            fontName=font,
            fontSize=10,
            leading=17,
            textColor=colors.HexColor("#1f2937"),
            spaceAfter=6,
        )
    )
    base.add(
        ParagraphStyle(
            name="BriefSmall",
            parent=base["BodyText"],
            fontName=font,
            fontSize=9,
            leading=14,
            textColor=colors.HexColor("#2f3a4a"),
        )
    )
    return base


def build_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def sanitize_filename_part(value: Any, fallback: str = "未命名") -> str:
    text = "".join(ch for ch in str(value or fallback) if ch not in '\\/:*?"<>|#[]{}').strip()
    return (text or fallback).replace(" ", "")[:18]


def _text(value: Any, fallback: str = "暂无") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def _percent(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0
    if 0 < number <= 1:
        number *= 100
    return f"{number:.1f}%"


def _advice_text(value: Any) -> str:
    if isinstance(value, dict):
        parts = [
            value.get("risk_assessment") or value.get("riskAssessment"),
            value.get("verification"),
            value.get("response_strategy") or value.get("responseStrategy"),
        ]
        text = " ".join(str(part).strip() for part in parts if part)
        return text or "暂无处置建议。"
    return _text(value, "建议优先核验官方通报来源，持续关注高传播账号扩散情况，并对低可信度说法进行辟谣标注。")


def _propagation_items(propagation: Any) -> list[str]:
    if not isinstance(propagation, dict):
        return ["暂无传播节点数据。"]

    items = []
    key_nodes = propagation.get("key_nodes") or propagation.get("keyNodes") or []
    for node in key_nodes[:5]:
        if not isinstance(node, dict):
            continue
        role = _text(node.get("role"), "传播节点")
        author = _text(node.get("author"), "匿名")
        platform = _text(node.get("platform"), "未知平台")
        publish_time = _text(node.get("publish_time") or node.get("publishTime"), "时间未知")
        items.append(f"{role}：{author}（{platform}，{publish_time}）")

    top_influencers = propagation.get("top_influencers") or propagation.get("topInfluencers") or []
    for item in top_influencers[:3]:
        if not isinstance(item, dict):
            continue
        author = _text(item.get("author"), "匿名")
        platform = _text(item.get("platform"), "未知平台")
        influence = _text(item.get("influence"), "0")
        items.append(f"高影响账号：{author}（{platform}，影响力 {influence}）")

    return items or ["暂无传播节点数据。"]


def _platform_chain_text(propagation: Any) -> str:
    if not isinstance(propagation, dict):
        return "暂无平台传播路径。"
    platform_chain = propagation.get("platform_chain") or propagation.get("platformChain") or {}
    nodes = (platform_chain.get("nodes") if isinstance(platform_chain, dict) else []) or []
    names = [node.get("name") for node in nodes if isinstance(node, dict) and node.get("name")]
    return "平台路径：" + " → ".join(names) if names else "暂无平台传播路径。"


def _p(value: Any, style) -> Paragraph:
    return Paragraph(escape(_text(value)), style)


def _section(story: list, title: str, styles) -> None:
    story.append(Paragraph(escape(title), styles["BriefHeading"]))


def _table(rows: list[list[Any]], styles, widths: list[float] | None = None) -> Table:
    table = Table(
        [[_p(cell, styles["BriefSmall"]) for cell in row] for row in rows],
        colWidths=widths,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeae5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#152238")),
                ("GRID", (0, 0), (-1, -1), 0.65, colors.HexColor("#c8d6dd")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _decode_chart_data_url(data_url: Any) -> bytes | None:
    if not isinstance(data_url, str) or "," not in data_url:
        return None
    header, encoded = data_url.split(",", 1)
    if "base64" not in header or not any(token in header for token in ("image/png", "image/jpeg", "image/jpg")):
        return None
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None
    if not raw or len(raw) > MAX_CHART_BYTES:
        return None
    return raw


def _chart_flowables(charts: list[dict], styles, max_width: float) -> list:
    flowables = []
    for chart in charts[:8]:
        if not isinstance(chart, dict):
            continue
        raw = _decode_chart_data_url(chart.get("data_url") or chart.get("dataUrl"))
        if not raw:
            continue
        try:
            reader = ImageReader(BytesIO(raw))
            image_width, image_height = reader.getSize()
        except Exception:
            continue
        if image_width <= 0 or image_height <= 0:
            continue

        max_height = 88 * mm
        scale = min(max_width / image_width, max_height / image_height)
        display_width = image_width * scale
        display_height = image_height * scale
        title = _text(chart.get("title"), "图表")

        flowables.append(
            KeepTogether(
                [
                    Paragraph(escape(title), styles["BriefSmall"]),
                    Spacer(1, 3),
                    RLImage(BytesIO(raw), width=display_width, height=display_height),
                    Spacer(1, 8),
                ]
            )
        )
    return flowables


def _build_pdf(title: str, subtitle: str, meta_rows: list[list[Any]], metrics: list[list[Any]], sections: list[dict]) -> bytes:
    buffer = BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
    )
    story = [
        Paragraph(escape(title), styles["BriefTitle"]),
        Paragraph(escape(subtitle), styles["BriefSubtitle"]),
    ]

    if meta_rows:
        story.append(_table([["项目", "内容"], *meta_rows], styles, [38 * mm, 122 * mm]))
        story.append(Spacer(1, 8))

    if metrics:
        story.append(_table([["指标", "数值", "说明"], *metrics], styles, [42 * mm, 42 * mm, 76 * mm]))
        story.append(Spacer(1, 8))

    for section in sections:
        _section(story, section["title"], styles)
        for paragraph in section.get("paragraphs", []):
            story.append(Paragraph(escape(_text(paragraph)), styles["BriefBody"]))
        if section.get("rows"):
            story.append(_table(section["rows"], styles, [46 * mm, 114 * mm]))
        if section.get("items"):
            item_rows = [["序号", "内容"], *[[index + 1, item] for index, item in enumerate(section["items"])]]
            story.append(_table(item_rows, styles, [14 * mm, 146 * mm]))
        if section.get("charts"):
            story.extend(_chart_flowables(section["charts"], styles, doc.width))

    story.append(Spacer(1, 16))
    story.append(Paragraph("由 Trendsight 自动生成", styles["BriefSmall"]))
    doc.build(story)
    return buffer.getvalue()


def generate_dashboard_brief_pdf(data: dict, filters: dict) -> bytes:
    timestamp = build_timestamp()
    items = data.get("items", [])
    pagination = data.get("pagination", {})
    high_risk = [item for item in items if item.get("risk_level") in {"high", "mid_high"}]
    metrics = [
        ["监测事件总数", pagination.get("total", len(items)), "当前筛选范围内事件总量"],
        ["高风险事件", len(high_risk), "本页高风险与中高风险事件数量"],
        ["当前页事件", len(items), "本次简报纳入的事件数量"],
    ]
    sections = [
        {
            "title": "热点事件列表",
            "items": [
                f"{item.get('title')}｜热度 {item.get('heat', 0)}｜风险 {item.get('risk_level', '未知')}｜报道 {item.get('report_count', 0)}"
                for item in items[:10]
            ],
        },
        {
            "title": "高风险待处理",
            "paragraphs": [] if high_risk else ["当前筛选范围内暂无高风险或中高风险事件。"],
            "items": [
                f"{item.get('title')}｜热度 {item.get('heat', 0)}｜阶段 {item.get('stage', '未知')}"
                for item in high_risk[:8]
            ],
        },
        {
            "title": "简短结论",
            "paragraphs": [
                f"当前看板共监测到 {pagination.get('total', len(items))} 条事件，"
                f"本页包含 {len(high_risk)} 条高风险或中高风险事件，建议优先核验高热度事件来源并持续观察扩散趋势。"
            ],
        },
    ]
    return _build_pdf(
        "Trendsight 事件看板简报",
        "基于当前事件看板筛选条件自动生成",
        [
            ["生成时间", timestamp],
            ["排序", filters.get("sort", "heat")],
            ["风险筛选", filters.get("risk_level") or "全部"],
            ["搜索词", filters.get("q") or "无"],
        ],
        metrics,
        sections,
    )


def generate_event_brief_pdf(event: dict, charts: list[dict] | None = None) -> bytes:
    timestamp = build_timestamp()
    sentiment = event.get("sentiment") or {}
    platforms = event.get("platform_distribution") or []
    keywords = event.get("keywords") or []
    trend_daily = event.get("trend_daily") or []
    authenticity = event.get("authenticity") or {}
    propagation = event.get("propagation") or {}
    people = event.get("people") or {}

    metrics = [
        ["热度指数", event.get("heat", 0), "当前事件热度"],
        ["累计报道", event.get("report_count", 0), "纳入分析的报道量"],
        ["风险等级", event.get("risk_level") or "未知", "算法识别风险等级"],
        ["生命周期", event.get("stage") or "未知", "事件当前传播阶段"],
        ["真实性置信", _percent(authenticity.get("credibility_score", event.get("confidence"))), "真实性检测综合分"],
        ["重复率", _percent(event.get("duplicate_rate")), "重复文本占比"],
    ]

    chart_sections = []
    if charts is not None:
        chart_sections.append(
            {
                "title": "图表快照",
                "paragraphs": [] if charts else ["本次导出未收到前端图表快照。"],
                "charts": charts or [],
            }
        )

    sections = [
        {
            "title": "事件概览",
            "paragraphs": [event.get("summary") or event.get("analysis") or "暂无事件概述。"],
            "rows": [
                ["事件时间", event.get("event_time") or "暂无"],
                ["发生地点", event.get("location") or "暂无"],
                ["直接起因", event.get("cause") or "暂无"],
                ["涉事主体", "、".join(people.values()) if isinstance(people, dict) and people else "暂无"],
            ],
        },
        {
            "title": "舆情分析",
            "rows": [
                ["积极情绪", _percent(sentiment.get("positive"))],
                ["中性情绪", _percent(sentiment.get("neutral"))],
                ["消极情绪", _percent(sentiment.get("negative"))],
            ],
        },
        {
            "title": "主要平台分布",
            "items": [f"{item.get('platform_name', '未知平台')}：{_percent(item.get('ratio'))}" for item in platforms],
        },
        {
            "title": "关键词",
            "items": [f"{item.get('word', '')}｜权重 {item.get('weight', 0)}" for item in keywords[:8]],
        },
        {
            "title": "趋势判断",
            "paragraphs": [
                f"当前趋势数据共 {len(trend_daily)} 个节点，"
                f"{'包含预测数据，建议持续观察后续走势。' if any(item.get('is_predicted') for item in trend_daily) else '以实际观测数据为主。'}"
            ],
        },
        *chart_sections,
        {
            "title": "传播线索",
            "paragraphs": [_platform_chain_text(propagation)],
            "items": _propagation_items(propagation),
        },
        {
            "title": "虚假文本检测",
            "rows": [
                ["官方来源比例", _percent(authenticity.get("official_ratio"))],
                ["已认证来源比例", _percent(authenticity.get("verified_ratio"))],
                ["普通用户比例", _percent(authenticity.get("plain_user_ratio"))],
            ],
            "paragraphs": ["真实性字段尚未接入时，该模块会显示为 0.0%，需等待算法写入 authenticity 数据。"],
        },
        {
            "title": "处置建议",
            "paragraphs": [_advice_text(event.get("advice"))],
        },
    ]

    return _build_pdf(
        "Trendsight 事件分析简报",
        event.get("title") or "未命名事件",
        [
            ["生成时间", timestamp],
            ["事件 ID", event.get("event_id", "")],
            ["事件标题", event.get("title", "未命名事件")],
        ],
        metrics,
        sections,
    )
