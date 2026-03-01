import enum
from datetime import date, datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cfs_routes.database import Base


class CycleStatus(str, enum.Enum):
    pending = "pending"
    fetched = "fetched"
    parsed = "parsed"
    failed = "failed"


class AiracCycle(Base):
    __tablename__ = "airac_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_ident: Mapped[str] = mapped_column(String(4), unique=True, nullable=False)
    effective_date: Mapped[date] = mapped_column(nullable=False)
    expiry_date: Mapped[date] = mapped_column(nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[CycleStatus] = mapped_column(
        Enum(CycleStatus), default=CycleStatus.pending, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    mandatory_routes: Mapped[list["MandatoryRoute"]] = relationship(
        back_populates="cycle", cascade="all, delete-orphan"
    )
    pdf: Mapped["AiracCyclePdf | None"] = relationship(
        back_populates="cycle", cascade="all, delete-orphan", uselist=False
    )


class AiracCyclePdf(Base):
    __tablename__ = "airac_cycle_pdfs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("airac_cycles.id"), nullable=False, unique=True)
    pdf_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    cycle: Mapped[AiracCycle] = relationship(back_populates="pdf")


class MandatoryRoute(Base):
    __tablename__ = "mandatory_routes"
    __table_args__ = (
        Index("ix_mr_cycle_airport", "cycle_id", "airport"),
        Index("ix_mr_cycle_airport_dir", "cycle_id", "airport", "direction_type"),
        Index("ix_mr_cycle_dest", "cycle_id", "destination"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("airac_cycles.id"), nullable=False)
    fir_code: Mapped[str] = mapped_column(String(4), nullable=False)
    airport: Mapped[str] = mapped_column(String(4), nullable=False)
    altitude: Mapped[str] = mapped_column(String(8), nullable=False)   # H, L, H&L
    direction_type: Mapped[str] = mapped_column(String(4), nullable=False)  # ARR, DEP, OVFL
    direction: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    destination: Mapped[str | None] = mapped_column(String(4), nullable=True)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    procedure: Mapped[str | None] = mapped_column(String(16), nullable=True)
    route: Mapped[str] = mapped_column(Text, nullable=False)
    raw_line: Mapped[str] = mapped_column(Text, nullable=False)

    cycle: Mapped[AiracCycle] = relationship(back_populates="mandatory_routes")
