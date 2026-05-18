from datetime import datetime, timezone
from typing import List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    github_username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    github_avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    github_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    github_bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    github_location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    github_blog: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    public_repos: Mapped[int] = mapped_column(Integer, default=0)
    followers: Mapped[int] = mapped_column(Integer, default=0)

    # Skill fingerprint stored as JSON and vector
    skill_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    skill_vector: Mapped[Optional[List[float]]] = mapped_column(Vector(128), nullable=True)
    skill_last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    saved_issues: Mapped[List["SavedIssue"]] = relationship("SavedIssue", back_populates="user")
    saved_searches: Mapped[List["SavedSearch"]] = relationship("SavedSearch", back_populates="user")


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_login: Mapped[str] = mapped_column(String(100), index=True)
    html_url: Mapped[str] = mapped_column(String(500))
    stars: Mapped[int] = mapped_column(Integer, default=0, index=True)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    open_issues_count: Mapped[int] = mapped_column(Integer, default=0)
    primary_language: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    topics: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    last_indexed: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    issues: Mapped[List["Issue"]] = relationship("Issue", back_populates="repository")


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    github_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    html_url: Mapped[str] = mapped_column(String(500))
    state: Mapped[str] = mapped_column(String(20), default="open", index=True)

    # Labels and classification
    labels: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    is_good_first_issue: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_help_wanted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Required skills extracted from issue
    required_skills: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    skill_vector: Mapped[Optional[List[float]]] = mapped_column(Vector(128), nullable=True)
    complexity_score: Mapped[float] = mapped_column(Float, default=0.5)

    # GitHub metadata
    comments: Mapped[int] = mapped_column(Integer, default=0)
    author_login: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Foreign key
    repository_id: Mapped[int] = mapped_column(Integer, ForeignKey("repositories.id"), index=True)
    repository: Mapped["Repository"] = relationship("Repository", back_populates="issues")

    # Relationships
    saved_by: Mapped[List["SavedIssue"]] = relationship("SavedIssue", back_populates="issue")


class SavedIssue(Base):
    __tablename__ = "saved_issues"
    __table_args__ = (UniqueConstraint("user_id", "issue_id", name="uq_user_issue"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    issue_id: Mapped[int] = mapped_column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String(50), default="saved")  # saved, in_progress, done

    user: Mapped["User"] = relationship("User", back_populates="saved_issues")
    issue: Mapped["Issue"] = relationship("Issue", back_populates="saved_by")


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    query: Mapped[str] = mapped_column(String(500))
    filters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    notify: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User")
