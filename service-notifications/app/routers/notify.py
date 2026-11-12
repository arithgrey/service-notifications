from fastapi import APIRouter, Depends, HTTPException
from app.schemas.order_event import OrderEventPayload
from app.services.slack import SlackNotifier
from app.dependencies import get_notifier

router = APIRouter()


@router.post("/notify/order", status_code=200)
def notify_order(
    payload: OrderEventPayload,
    notifier: SlackNotifier = Depends(get_notifier),
):
    success = notifier.send(payload)
    if not success:
        raise HTTPException(status_code=502, detail="Slack webhook failed")
    return {"ok": True}
