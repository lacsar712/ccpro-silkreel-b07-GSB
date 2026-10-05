"""缫丝盆门槛：标成已缫完须最近一次汤温落在 38～42℃。

另规定：
- 「已缫完」次数台只认成功改态那一笔事件（StatusChange），
  不认盆当前状态，也不认历史汤温颗数。
- 每口盆每进入一轮「缫丝中」轮次号加 1；同一轮里的「已缫完」
  成功事件靠数据库部分唯一索引兜底，两名工并发只能落一笔。
- 「今日」按服务器所在自然日（Asia/Shanghai）切，不按 UTC 日切。
"""

from datetime import datetime, timedelta, timezone

from app.models import Basin

MIN_TEMP = 38.0
MAX_TEMP = 42.0

# 服务器自然日按东八区切（中国 1991 年起无夏令时，固定 +8 即准，
# 不依赖镜像里是否装了 tzdata）。
SERVER_TZ = timezone(timedelta(hours=8), name="CST")


class RuleError(ValueError):
    pass


def latest_temp(basin: Basin) -> float | None:
    if not basin.readings:
        return None
    latest = max(basin.readings, key=lambda r: r.taken_at)
    return latest.water_temp_c


def assert_can_set_status(basin: Basin, new_status: str) -> None:
    allowed = {Basin.STATUS_SOAKING, Basin.STATUS_REELING, Basin.STATUS_REELED}
    if new_status not in allowed:
        raise RuleError(f"无效状态：{new_status}")
    if new_status != Basin.STATUS_REELED:
        return
    temp = latest_temp(basin)
    if temp is None:
        raise RuleError("该盆尚无汤温记录，不能标已缫完")
    if temp < MIN_TEMP or temp > MAX_TEMP:
        raise RuleError(
            f"最近汤温 {temp}℃ 不在 {MIN_TEMP:.0f}～{MAX_TEMP:.0f}℃，不能标已缫完"
        )


def next_round_on_enter_reeling(basin: Basin, new_status: str) -> bool:
    """进入新一轮「缫丝中」时轮次号加 1（同态不递增）。"""
    return new_status == Basin.STATUS_REELING and basin.status != Basin.STATUS_REELING


def server_day_window(now: datetime | None = None) -> tuple[datetime, datetime, str]:
    """返回服务器自然日的 [起, 止)（UTC，aware）与本地日期串。"""
    now = now or datetime.now(SERVER_TZ)
    local_now = now.astimezone(SERVER_TZ)
    start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(timezone.utc),
        end_local.astimezone(timezone.utc),
        start_local.date().isoformat(),
    )
