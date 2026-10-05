from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def server_today() -> date:
    """服务器自然日（应用服务器本地日期）。"""
    return date.today()


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


class ReeledEvent(Base):
    """一次「成功改成已缫完」的流水，与改态同一事务写入；次数台按服务器自然日统计它。"""

    __tablename__ = "reeled_events"
    __table_args__ = (Index("ix_reeled_events_day", "day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    basin_id: Mapped[int] = mapped_column(ForeignKey("basins.id"))
    operator: Mapped[str] = mapped_column(String(64), default="")
    happened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    day: Mapped[date] = mapped_column(Date, default=server_today)
