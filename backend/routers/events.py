from fastapi import APIRouter, Depends, HTTPException, status
from io import BytesIO
from urllib.parse import quote

from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from dependencies import get_db
from utils.algo_client import call_algo
from services.event_service import save_event, get_events, get_event_detail
from services.brief_pdf_service import build_timestamp, generate_dashboard_brief_pdf, generate_event_brief_pdf, sanitize_filename_part


class AnalyzeRequest(BaseModel):
    documents: list[dict]
    comments: list[dict] = []
    sentiment_method: str = "bert"

class AnalyzeResponseData(BaseModel):
    count: int
    event_ids: list[int]

class AnalyzeResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: AnalyzeResponseData


class EventListItem(BaseModel):
    event_id: int
    title: str
    heat: float | None = None
    report_count: int | None = None
    risk_level: str | None = None
    stage: str | None = None
    event_time: str | None = None
    created_at: str | None = None
    summary: str | None = None
    location: str | None = None
    analysis: str | None = None
    positive: float | None = None
    neutral: float | None = None
    negative: float | None = None
    keywords: list[str] = []

class PaginationData(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int

class EventListData(BaseModel):
    items: list[EventListItem]
    pagination: PaginationData

class EventListResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: EventListData


class EventSentiment(BaseModel):
    positive: float
    neutral: float
    negative: float


class EventStageProbability(BaseModel):
    latent: float
    growth: float
    peak: float
    decline: float


class EventKeywordItem(BaseModel):
    word: str
    weight: float
    rank: int


class EventPlatformItem(BaseModel):
    platform_name: str
    ratio: float
    rank: int


class EventTrendDailyItem(BaseModel):
    date: str | None = None
    count: int
    is_predicted: int = 0
    predict_heat: float | None = None
    predict_count: int | None = None


class EventDetailData(BaseModel):
    event_id: int
    title: str
    heat: float | None = None
    report_count: int | None = None
    risk_level: str | None = None
    stage: str | None = None
    confidence: float | None = None
    analysis: str | None = None
    event_time: str | None = None
    created_at: str | None = None
    sentiment: EventSentiment | None = None
    stage_probability: EventStageProbability | None = None
    sources: list[str] | None = None
    time_start: str | None = None
    time_end: str | None = None
    keywords: list[EventKeywordItem] = []
    platform_distribution: list[EventPlatformItem] = []
    trend: list[dict] = []
    future_trend: list[dict] = []
    authenticity: dict | None = None
    propagation: dict | None = None
    authenticity_level: str | None = None
    authenticity_label: str | None = None
    authenticity_description: str | None = None
    duplicate_rate: float | None = None
    similar_events: list[dict] = []
    advice: dict | None = None
    summary: str | None = None
    location: str | None = None
    cause: str | None = None
    people: dict | None = None
    trend_daily: list[EventTrendDailyItem] = []


class EventDetailResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: EventDetailData | None = None


router = APIRouter()


def pdf_response(content: bytes, filename: str) -> StreamingResponse:
    encoded = quote(filename)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


@router.post("/api/events/analyze", response_model=AnalyzeResponse)
def analyze_events(
    request: AnalyzeRequest,
    db: Session = Depends(get_db),
):
    try:
        results = call_algo(
            documents=request.documents,
            comments=request.comments,
            sentiment_method=request.sentiment_method,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )

    event_ids = []
    for report in results:
        event = save_event(db, report)
        event_ids.append(event.event_id)

    return AnalyzeResponse(
        data=AnalyzeResponseData(
            count=len(event_ids),
            event_ids=event_ids,
        )
    )


@router.get("/api/events", response_model=EventListResponse)
def list_events(
    page: int = 1,
    size: int = 20,
    sort: str = 'heat',
    risk_level: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    data = get_events(db, page=page, size=size, sort=sort, risk_level=risk_level, q=q)
    return EventListResponse(data=data)


@router.get("/api/events/hot", response_model=EventListResponse)
def hot_events(
    page: int = 1,
    size: int = 20,
    sort: str = 'heat',
    risk_level: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    data = get_events(db, page=page, size=size, sort=sort, risk_level=risk_level, q=q)
    return EventListResponse(data=data)


@router.get("/api/events/brief/dashboard.pdf")
def dashboard_brief_pdf(
    page: int = 1,
    size: int = 20,
    sort: str = 'heat',
    risk_level: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    data = get_events(db, page=page, size=min(size, 50), sort=sort, risk_level=risk_level, q=q)
    content = generate_dashboard_brief_pdf(
        data,
        {
            "sort": sort,
            "risk_level": risk_level,
            "q": q,
        },
    )
    return pdf_response(content, f"Trendsight-事件看板简报-{build_timestamp()}.pdf")


@router.get("/api/events/{event_id}/brief.pdf")
def event_brief_pdf(
    event_id: int,
    db: Session = Depends(get_db),
):
    data = get_event_detail(db, event_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="事件不存在",
        )
    content = generate_event_brief_pdf(data)
    title = sanitize_filename_part(data.get("title"), "未命名事件")
    return pdf_response(content, f"Trendsight-事件简报-{title}-{build_timestamp()}.pdf")


@router.get("/api/events/{event_id}", response_model=EventDetailResponse)
def event_detail(
    event_id: int,
    db: Session = Depends(get_db),
):
    data = get_event_detail(db, event_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="事件不存在",
        )
    return EventDetailResponse(data=data)
