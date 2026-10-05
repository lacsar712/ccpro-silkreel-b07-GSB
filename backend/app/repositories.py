from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Basin, BathReading, Filature, ReeledEvent, User


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

    async def add_reading(self, basin: Basin, temp_c: float, operator: str) -> BathReading:
        row = BathReading(basin=basin, water_temp_c=temp_c, operator=operator)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def save_status(self, basin: Basin, status: str) -> None:
        basin.status = status
        await self.session.commit()

    async def mark_reeled_once(self, basin: Basin, operator: str) -> bool:
        """把盆原子地标成已缫完，并在同一事务里记一笔流水。

        并发下只有一笔 UPDATE 能命中「尚未已缫完」的行：赢家提交后，
        输家的 WHERE 重新求值命中 0 行，回滚返回 False，次数台不多计。
        """
        result = await self.session.execute(
            update(Basin)
            .where(Basin.id == basin.id, Basin.status != Basin.STATUS_REELED)
            .values(status=Basin.STATUS_REELED)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            await self.session.rollback()
            return False
        self.session.add(ReeledEvent(basin_id=basin.id, operator=operator))
        await self.session.commit()
        self.session.expire(basin)
        return True


class ReeledEventRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def day_rows(self, day: date) -> list[tuple[ReeledEvent, str]]:
        result = await self.session.execute(
            select(ReeledEvent, Basin.code)
            .join(Basin, ReeledEvent.basin_id == Basin.id)
            .where(ReeledEvent.day == day)
            .order_by(ReeledEvent.id.desc())
        )
        return list(result.all())
