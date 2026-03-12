from sqlalchemy import Text, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from db import Base

class Page(Base):
    __tablename__ = "pages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=True)
    meta_description: Mapped[str] = mapped_column(Text, nullable=True)
    emails: Mapped[str] = mapped_column(Text, nullable=True)   # CSV
    phones: Mapped[str] = mapped_column(Text, nullable=True)   # CSV
    forms: Mapped[str] = mapped_column(Text, nullable=True)    # JSON string
    fetched_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())

class EmailDraft(Base):
    __tablename__ = "email_drafts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    target_email: Mapped[str] = mapped_column(Text, nullable=True)
    target_name: Mapped[str] = mapped_column(Text, nullable=True)
    company_name: Mapped[str] = mapped_column(Text, nullable=True)
    context_tier: Mapped[str] = mapped_column(Text, nullable=True, default="medium")
    original_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    subject: Mapped[str] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=True, default="draft")
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=True)

