# backend/ws.py
"""WebSocket 连接管理器：实时推送测试执行进度"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# 活跃连接：{ run_id: [websocket, ...] }
_active_connections: dict[int, list[WebSocket]] = {}

# Pipeline 活跃连接：{ pipeline_id: [websocket, ...] }
# 与 _active_connections 分离，避免 run_id 与 pipeline_id 整数 ID 碰撞
_pipeline_connections: dict[int, list[WebSocket]] = {}

# 全局连接（用于 slot_update 等全局事件）
_global_connections: list[WebSocket] = []


# ---------------------------------------------------------------------------
# Run 连接管理
# ---------------------------------------------------------------------------

async def connect(run_id: int, ws: WebSocket):
    """接受 WebSocket 连接并注册到 run"""
    await ws.accept()
    if run_id not in _active_connections:
        _active_connections[run_id] = []
    _active_connections[run_id].append(ws)


async def disconnect(run_id: int, ws: WebSocket):
    """移除 run 的 WebSocket 连接"""
    if run_id in _active_connections:
        _active_connections[run_id] = [
            w for w in _active_connections[run_id] if w != ws
        ]
        if not _active_connections[run_id]:
            del _active_connections[run_id]


async def broadcast(run_id: int, event: str, data: dict):
    """向关注某个 run 的所有客户端广播消息"""
    message = json.dumps({"event": event, "data": data}, default=str)
    dead: list[WebSocket] = []
    for ws in _active_connections.get(run_id, []):
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    # 清理断开的连接
    if dead and run_id in _active_connections:
        _active_connections[run_id] = [
            w for w in _active_connections[run_id] if w not in dead
        ]
        if not _active_connections[run_id]:
            del _active_connections[run_id]


@router.websocket("/ws/runs/{run_id}")
async def ws_run_progress(ws: WebSocket, run_id: int):
    """WebSocket 端点：实时推送测试运行进度"""
    await connect(run_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await disconnect(run_id, ws)


# ---------------------------------------------------------------------------
# Pipeline 连接管理
# ---------------------------------------------------------------------------

async def connect_pipeline(pipeline_id: int, ws: WebSocket):
    """接受 WebSocket 连接并注册到 pipeline"""
    await ws.accept()
    if pipeline_id not in _pipeline_connections:
        _pipeline_connections[pipeline_id] = []
    _pipeline_connections[pipeline_id].append(ws)


async def disconnect_pipeline(pipeline_id: int, ws: WebSocket):
    """移除 pipeline 的 WebSocket 连接"""
    if pipeline_id in _pipeline_connections:
        _pipeline_connections[pipeline_id] = [
            w for w in _pipeline_connections[pipeline_id] if w != ws
        ]
        if not _pipeline_connections[pipeline_id]:
            del _pipeline_connections[pipeline_id]


async def broadcast_pipeline(pipeline_id: int, event: str, data: dict):
    """向关注某个 pipeline 的所有客户端广播"""
    message = json.dumps({"event": event, "data": data}, default=str)
    dead: list[WebSocket] = []
    for ws in _pipeline_connections.get(pipeline_id, []):
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    # 清理断开的连接
    if dead and pipeline_id in _pipeline_connections:
        _pipeline_connections[pipeline_id] = [
            w for w in _pipeline_connections[pipeline_id] if w not in dead
        ]
        if not _pipeline_connections[pipeline_id]:
            del _pipeline_connections[pipeline_id]


@router.websocket("/ws/pipelines/{pipeline_id}")
async def ws_pipeline_progress(ws: WebSocket, pipeline_id: int):
    """WebSocket 端点：实时推送 Pipeline 进度"""
    await connect_pipeline(pipeline_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await disconnect_pipeline(pipeline_id, ws)


# ---------------------------------------------------------------------------
# 全局连接管理
# ---------------------------------------------------------------------------

async def connect_global(ws: WebSocket):
    """注册全局 WebSocket 连接"""
    await ws.accept()
    _global_connections.append(ws)


async def disconnect_global(ws: WebSocket):
    """移除全局 WebSocket 连接"""
    if ws in _global_connections:
        _global_connections.remove(ws)


async def broadcast_global(event: str, data: dict):
    """向所有客户端广播（全局事件）"""
    message = json.dumps({"event": event, "data": data}, default=str)

    # 1. 全局连接
    dead: list[WebSocket] = []
    for ws in _global_connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _global_connections.remove(ws)

    # 2. Run 连接（兼容现有看板）
    dead_run_ids: list[int] = []
    for run_id, conns in _active_connections.items():
        dead_in_run: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead_in_run.append(ws)
        if dead_in_run:
            _active_connections[run_id] = [
                w for w in conns if w not in dead_in_run
            ]
            if not _active_connections[run_id]:
                dead_run_ids.append(run_id)
    for rid in dead_run_ids:
        del _active_connections[rid]

    # 3. Pipeline 连接
    dead_pipeline_ids: list[int] = []
    for pid, conns in _pipeline_connections.items():
        dead_in_pipeline: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead_in_pipeline.append(ws)
        if dead_in_pipeline:
            _pipeline_connections[pid] = [
                w for w in conns if w not in dead_in_pipeline
            ]
            if not _pipeline_connections[pid]:
                dead_pipeline_ids.append(pid)
    for pid in dead_pipeline_ids:
        del _pipeline_connections[pid]


@router.websocket("/ws/global")
async def ws_global_events(ws: WebSocket):
    """WebSocket 端点：全局事件推送（Slot 状态变化等）"""
    await connect_global(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await disconnect_global(ws)
