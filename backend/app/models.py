from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20), default="worker")


class Filature(Base):
    __tablename__ = "filatures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    riverside: Mapped[str] = mapped_column(String(120), default="")
    basins: Mapped[list["Basin"]] = relationship(back_populates="filature")


class Basin(Base):
    __tablename__ = "basins"
    __table_args__ = (UniqueConstraint("filature_id", "code"),)

    STATUS_SOAKING = "soaking"
    STATUS_REELING = "reeling"
    STATUS_REELED = "reeled"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filature_id: Mapped[int] = mapped_column(ForeignKey("filatures.id"))
    code: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default=STATUS_SOAKING)
    ring_index: Mapped[int] = mapped_column(Integer, default=0)
    # 缫丝轮次：每次重新进入「缫丝中」加 1。配合 status_changes 的唯一约束，
    # 同一轮里两名工交叉点「已缫完」只能落一笔。
    reel_round: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    filature: Mapped[Filature] = relationship(back_populates="basins")
    readings: Mapped[list["BathReading"]] = relationship(back_populates="basin")


class BathReading(Base):
    __tablename__ = "bath_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    basin_id: Mapped[int] = mapped_column(ForeignKey("basins.id"))
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    water_temp_c: Mapped[float] = mapped_column(Float)
    operator: Mapped[str] = mapped_column(String(64), default="")
    basin: Mapped[Basin] = relationship(back_populates="readings")


class StatusChange(Base):
    """每次盆态变更留一笔；「已缫完」次数台按今日成功笔数统计。"""

    __tablename__ = "status_changes"
    __table_args__ = (
        # 同一盆同一轮缫丝，只允许一笔「已缫完」成功事件。
        # 两名工并发点已缫完时，数据库直接顶回第二笔，次数台只加 1。
        # 部分索引：只锁「已缫完」，其余改态一轮里仍可反复记录。
        Index(
            "uq_reeled_once_per_round",
            "basin_id",
            "reel_round",
            unique=True,
            postgresql_where=text("to_status = 'reeled'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    basin_id: Mapped[int] = mapped_column(ForeignKey("basins.id"))
    reel_round: Mapped[int] = mapped_column(Integer, nullable=False)
    from_status: Mapped[str] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    operator: Mapped[str] = mapped_column(String(64), default="")
