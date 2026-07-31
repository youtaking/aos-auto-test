# backend/ws.py
"""WebSocket 连接管理器：实时推送测试执行进度"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# 活跃连接：{ run_id: [websocket, ...] }
_active_connections: dict[int, list[WebSocket]] = {}


async def connect(run_id: int, ws: WebSocket):
    """接受 WebSocket 连接并注册"""
    await ws.accept()
    if run_id not in _active_connections:
        _active_connections[run_id] = []
    _active_connections[run_id].append(ws)


async def disconnect(run_id: int, ws: WebSocket):
    """移除 WebSocket 连接"""
    if run_id in _active_connections:
        _active_connections[run_id] = [
            w for w in _active_connections[run_id] if w != ws
        ]
        if not _active_connections[run_id]:
            del _active_connections[run_id]


async def broadcast(run_id: int, event: str, data: dict):
    """向关注某个 run 的所有客户端广播消息"""
    message = json.dumps({"event": event, "data": data}, default=str)
    for ws in _active_connections.get(run_id, []):
        try:
            await ws.send_text(message)
        except Exception:
            pass


@router.websocket("/ws/runs/{run_id}")
async def ws_run_progress(ws: WebSocket, run_id: int):
    """WebSocket 端点：实时推送测试运行进度"""
    await connect(run_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await disconnect(run_id, ws)
