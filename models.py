from sqlalchemy import ForeignKey, DateTime, func, Boolean, DateTime
from init_db import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str] = mapped_column(nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(nullable=True)
    email: Mapped[str] = mapped_column(nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verify_code: Mapped[str | None] = mapped_column(nullable=True)
    verify_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reset_code: Mapped[str | None] = mapped_column(nullable=True)
    reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    posts: Mapped[list['Post']] = relationship(back_populates='author', cascade='all, delete-orphan')

class Post(Base):
    __tablename__ = 'posts'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="Cascade"), nullable=False)
    title: Mapped[str | None] = mapped_column(nullable=True)
    media_url: Mapped[str | None] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    author: Mapped["User"] = relationship(back_populates='posts')