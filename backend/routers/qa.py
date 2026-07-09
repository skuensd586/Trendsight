from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dependencies import get_db, get_current_user
from schemas.qa import QARequest, QAResponse, QAResponseData, HistoryResponse, HistoryResponseData
from services.qa_service import ask_question, get_history

router = APIRouter()


@router.post("/api/events/{event_id}/qa", response_model=QAResponse)
def qa_ask(
    request: QARequest,
    event_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        data = ask_question(
            db=db,
            user_id=user_id,
            event_id=event_id,
            question=request.question,
            conversation_id=request.conversation_id,
        )
        return QAResponse(data=QAResponseData(**data))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/api/qa/history/{conversation_id}", response_model=HistoryResponse)
def qa_history(
    conversation_id: str,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        data = get_history(db=db, user_id=user_id, conversation_id=conversation_id)
        return HistoryResponse(data=HistoryResponseData(**data))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
