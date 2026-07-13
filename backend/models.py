"""ORM models. Researcher-only (no admin/role). Portable across SQLite (dev) and Postgres (prod)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    queries: Mapped[list["Query"]] = relationship(back_populates="user")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # sha256 hex
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Query(Base):
    __tablename__ = "queries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    raw_query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    retrieval_mode: Mapped[str] = mapped_column(String(20), default="hybrid")
    reasoning_mode: Mapped[str] = mapped_column(String(20), default="graph")
    flags: Mapped[list] = mapped_column(JSON, default=list)
    narrative_md: Mapped[str | None] = mapped_column(Text)
    explanation_md: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="queries")
    claims: Mapped[list["Claim"]] = relationship(back_populates="query", cascade="all, delete-orphan")
    stage_logs: Mapped[list["StageLog"]] = relationship(back_populates="query", cascade="all, delete-orphan")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    query_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("queries.id", ondelete="CASCADE"), index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_strength: Mapped[str] = mapped_column(String(20), default="moderate")  # high/moderate/low
    consensus_label: Mapped[str] = mapped_column(String(20), default="consensus")   # consensus/contested/insufficient
    is_abstention: Mapped[bool] = mapped_column(Boolean, default=False)
    order_idx: Mapped[int] = mapped_column(Integer, default=0)

    query: Mapped[Query] = relationship(back_populates="claims")
    citations: Mapped[list["Citation"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    provenance: Mapped[list["Provenance"]] = relationship(back_populates="claim", cascade="all, delete-orphan")


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(20), default="pubmed")
    source_ref: Mapped[str] = mapped_column(String(64))     # PMID
    title: Mapped[str | None] = mapped_column(Text)
    journal: Mapped[str | None] = mapped_column(String(300))
    snippet: Mapped[str | None] = mapped_column(Text)
    relevance: Mapped[int] = mapped_column(Integer, default=0)
    contested: Mapped[bool] = mapped_column(Boolean, default=False)

    claim: Mapped[Claim] = relationship(back_populates="citations")


class Provenance(Base):
    __tablename__ = "provenance"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[str] = mapped_column(String(40))
    prompt_version: Mapped[str] = mapped_column(String(40), default="v1")
    model_id: Mapped[str] = mapped_column(String(80))
    retrieval_pass: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    claim: Mapped[Claim] = relationship(back_populates="provenance")


class StageLog(Base):
    __tablename__ = "stage_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_uuid)
    query_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("queries.id", ondelete="CASCADE"), index=True)
    stage_no: Mapped[str] = mapped_column(String(8))
    agent_id: Mapped[str] = mapped_column(String(40))
    model_id: Mapped[str | None] = mapped_column(String(80))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="ok")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    query: Mapped[Query] = relationship(back_populates="stage_logs")
