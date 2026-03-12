from sqlalchemy import Text, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from db import Base


class Page(Base):
    """Read-only mirror of the crawler's pages table."""
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=True)
    meta_description: Mapped[str] = mapped_column(Text, nullable=True)
    emails: Mapped[str] = mapped_column(Text, nullable=True)
    phones: Mapped[str] = mapped_column(Text, nullable=True)
    forms: Mapped[str] = mapped_column(Text, nullable=True)
    fetched_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ExportCheckpoint(Base):
    """Tracks incremental export position per export name."""
    __tablename__ = "export_checkpoints"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    last_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
