"""FastAPI app for the local poker simulator."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from poker_sim.engine import ActionType, PlayerAction, SessionConfig, bb_to_chips
from poker_sim.session import SessionController

app = FastAPI(title="Poker Simulator API")

SESSIONS: dict[str, SessionController] = {}


class CreateSessionRequest(BaseModel):
    hero_buyin_bb: int = Field(ge=10, le=100)
    reveal_all_cards_after_hand: bool = False


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/session")
def create_session(payload: CreateSessionRequest) -> dict[str, Any]:
    controller = SessionController(
        SessionConfig(
            hero_buyin_bb=payload.hero_buyin_bb,
            reveal_all_cards_after_hand=payload.reveal_all_cards_after_hand,
        )
    )
    controller.start()
    SESSIONS[controller.session_id] = controller
    return {"session_id": controller.session_id, "snapshot": controller.snapshot()}


@app.get("/api/session/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    controller = SESSIONS.get(session_id)
    if controller is None:
        raise HTTPException(status_code=404, detail="session not found")
    return controller.snapshot()


@app.websocket("/ws/session/{session_id}")
async def session_socket(websocket: WebSocket, session_id: str) -> None:
    controller = SESSIONS.get(session_id)
    if controller is None:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "session not found"})
        await websocket.close()
        return

    await websocket.accept()
    await websocket.send_json({"type": "state", "payload": controller.snapshot()})

    try:
        while True:
            message = await websocket.receive_json()
            try:
                payloads = await _handle_message(controller, message)
            except ValueError as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
                continue

            for snapshot in payloads:
                await websocket.send_json({"type": "state", "payload": snapshot})
                await asyncio.sleep(0.08)
    except WebSocketDisconnect:
        return


async def _handle_message(
    controller: SessionController, message: dict[str, Any]
) -> list[dict[str, object]]:
    message_type = message.get("type")
    if message_type == "next_hand":
        if not controller.snapshot()["hand_complete"]:
            raise ValueError("hand is still in progress")
        return controller.next_hand()

    if message_type != "action":
        raise ValueError("unsupported message type")

    action_name = message.get("action")
    amount_bb = message.get("amount_bb")
    action = _parse_action(action_name, amount_bb)
    return controller.apply_human_action(action)


def _parse_action(action_name: str | None, amount_bb: Any) -> PlayerAction:
    if action_name is None:
        raise ValueError("missing action")

    try:
        action_type = ActionType(action_name)
    except ValueError as exc:  # pragma: no cover
        raise ValueError("unknown action") from exc

    if action_type in {ActionType.BET, ActionType.RAISE_TO}:
        if amount_bb is None:
            raise ValueError("missing amount")
        return PlayerAction(action_type, amount=bb_to_chips(float(amount_bb)))

    return PlayerAction(action_type)
