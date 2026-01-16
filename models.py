from sqlalchemy import ForeignKey, DateTime, func, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from init_db import Base

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

from sqlalchemy import ForeignKey, DateTime, func, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from init_db import Base

class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)

    media_url: Mapped[str] = mapped_column(nullable=False)
    media_type: Mapped[str] = mapped_column(String(16), nullable=False, default="image")
    preview_url: Mapped[str | None] = mapped_column(nullable=True)

    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    author: Mapped["User"] = relationship(back_populates="posts")
