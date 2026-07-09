from pydantic import BaseModel


class QARequest(BaseModel):
    conversation_id: str | None = None
    question: str


class QAResponseData(BaseModel):
    conversation_id: str
    answer: str
    created_time: str


class QAResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: QAResponseData | None = None


class HistoryMessage(BaseModel):
    role: str
    content: str
    created_time: str


class HistoryResponseData(BaseModel):
    conversation_id: str
    messages: list[HistoryMessage]


class HistoryResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: HistoryResponseData | None = None
