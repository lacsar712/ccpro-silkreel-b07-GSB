from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Basin, BathReading, Filature, StatusChange, User


class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_username(self, username: str) -> User | None:
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()


class BasinRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def board(self) -> Filature | None:
        result = await self.session.execute(
            select(Filature).options(
                selectinload(Filature.basins).selectinload(Basin.readings)
            )
        )
        return result.scalars().first()

    async def get(self, basin_id: int) -> Basin | None:
        result = await self.session.execute(
            select(Basin)
            .options(selectinload(Basin.readings))
            .where(Basin.id == basin_id)
        )
        return result.scalar_one_or_none()

    async def get_for_update(self, basin_id: int) -> Basin | None:
        """SELECT ... FOR UPDATE：两名工交叉改同一口盆时在此排队。"""
        result = await self.session.execute(
            select(Basin)
            .options(selectinload(Basin.readings))
            .where(Basin.id == basin_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def add_reading(self, basin: Basin, temp_c: float, operator: str) -> BathReading:
        row = BathReading(basin=basin, water_temp_c=temp_c, operator=operator)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def change_status(
        self, basin: Basin, new_status: str, operator: str, bump_round: bool
    ) -> StatusChange:
        """改盆态并落一笔改态事件，同一事务提交。

        bump_round: 进入新一轮「缫丝中」时轮次号加 1。
        并发第二笔撞部分唯一索引时抛 IntegrityError，由路由回滚并顶回。
        """
        old_status = basin.status
        if bump_round:
            basin.reel_round += 1
        event = StatusChange(
            basin_id=basin.id,
            reel_round=basin.reel_round,
            from_status=old_status,
            to_status=new_status,
            operator=operator,
        )
        basin.status = new_status
        self.session.add(event)
        await self.session.commit()
        return event


class CounterRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def reeled_success_count(self, start_utc, end_utc) -> int:
        """统计 [start_utc, end_utc) 内成功落库的「标成已缫完」事件笔数。

        只点事件表，不看盆现状，也不看汤温记录。
        """
        result = await self.session.execute(
            select(func.count(StatusChange.id))
            .where(StatusChange.to_status == Basin.STATUS_REELED)
            .where(StatusChange.changed_at >= start_utc)
            .where(StatusChange.changed_at < end_utc)
        )
        return int(result.scalar_one())
