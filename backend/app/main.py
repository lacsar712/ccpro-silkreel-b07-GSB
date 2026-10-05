from quart import Quart, g, jsonify, request
from quart.helpers import make_response
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Basin
from app.repositories import BasinRepo, CounterRepo, UserRepo
from app.security import make_token, parse_token, verify_password
from app.services import (
    RuleError,
    assert_can_set_status,
    latest_temp,
    next_round_on_enter_reeling,
    server_day_window,
)

app = Quart(__name__)


def _bearer() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:]
    return None


@app.before_request
async def load_user():
    g.user = None
    token = _bearer()
    if not token:
        return
    username = parse_token(token)
    if not username:
        return
    async with SessionLocal() as session:
        g.user = await UserRepo(session).by_username(username)


def require_user():
    if g.user is None:
        return jsonify({"detail": "未登录"}), 401
    return None


@app.route("/api/health")
async def health():
    return {"status": "ok", "service": "SilkReel"}


@app.route("/api/auth/login", methods=["POST"])
async def login():
    body = await request.get_json(force=True)
    username = (body or {}).get("username", "")
    password = (body or {}).get("password", "")
    async with SessionLocal() as session:
        user = await UserRepo(session).by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            return jsonify({"detail": "用户名或密码错误"}), 401
        return {
            "access_token": make_token(user.username),
            "user": {"username": user.username, "role": user.role},
        }


@app.route("/api/auth/me")
async def me():
    denied = require_user()
    if denied:
        return denied
    return {"username": g.user.username, "role": g.user.role}


def _basin_json(basin: Basin) -> dict:
    return {
        "id": basin.id,
        "code": basin.code,
        "status": basin.status,
        "ringIndex": basin.ring_index,
        "latestTempC": latest_temp(basin),
        "readingCount": len(basin.readings or []),
    }


@app.route("/api/board")
async def board():
    denied = require_user()
    if denied:
        return denied
    async with SessionLocal() as session:
        mill = await BasinRepo(session).board()
        if mill is None:
            return jsonify({"detail": "尚无缫丝坞"}), 404
        basins = sorted(mill.basins, key=lambda b: b.ring_index)
        return {
            "filature": mill.name,
            "riverside": mill.riverside,
            "basins": [_basin_json(b) for b in basins],
        }


@app.route("/api/basins/<int:basin_id>/readings", methods=["POST"])
async def add_reading(basin_id: int):
    denied = require_user()
    if denied:
        return denied
    body = await request.get_json(force=True)
    try:
        temp = float((body or {}).get("waterTempC"))
    except (TypeError, ValueError):
        return jsonify({"detail": "汤温必须是数字"}), 400
    async with SessionLocal() as session:
        repo = BasinRepo(session)
        basin = await repo.get(basin_id)
        if basin is None:
            return jsonify({"detail": "盆不存在"}), 404
        await repo.add_reading(basin, temp, g.user.username)
        basin = await repo.get(basin_id)
        return _basin_json(basin)


@app.route("/api/basins/<int:basin_id>/status", methods=["POST"])
async def set_status(basin_id: int):
    denied = require_user()
    if denied:
        return denied
    body = await request.get_json(force=True)
    status = (body or {}).get("status", "")
    async with SessionLocal() as session:
        repo = BasinRepo(session)
        # 行锁串行化同一口盆的改态，配合事件表部分唯一索引：
        # 两名工交叉把同一口缫丝中盆标成已缫完，只许一笔成功。
        basin = await repo.get_for_update(basin_id)
        if basin is None:
            return jsonify({"detail": "盆不存在"}), 404
        try:
            assert_can_set_status(basin, status)
        except RuleError as exc:
            return jsonify({"detail": str(exc)}), 400
        bump = next_round_on_enter_reeling(basin, status)
        try:
            await repo.change_status(basin, status, g.user.username, bump)
        except IntegrityError:
            # 同一轮已有一笔成功的「已缫完」（并发抢标落败者）
            return jsonify({"detail": "该盆本轮已标过已缫完，只计一次"}), 409
        basin = await repo.get(basin_id)
        return _basin_json(basin)


@app.route("/api/counters/reeled-today")
async def reeled_today_counter():
    """已缫完次数台：今日（服务器自然日）成功改态成已缫完的笔数。

    只点成功改态事件，不随盆现状变动——改回缫丝中不会减，
    历史上早已缫完的盆也不充数。
    """
    denied = require_user()
    if denied:
        return denied
    start_utc, end_utc, day = server_day_window()
    async with SessionLocal() as session:
        count = await CounterRepo(session).reeled_success_count(start_utc, end_utc)
    return {"date": day, "reeledCount": count}
