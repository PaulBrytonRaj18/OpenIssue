"""Add performance indexes for production scale

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-19

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Issues: composite index for common filtered queries (state + repo)
    op.create_index("ix_issues_state_repo", "issues", ["state", "repository_id"])

    # Issues: index for sorting by updated_at (trending, search)
    op.create_index("ix_issues_updated_at", "issues", ["updated_at"])

    # Issues: composite for matching queries (state + skill_vector)
    op.create_index("ix_issues_state_vector", "issues", ["state"], postgresql_where=op.text("skill_vector IS NOT NULL"))

    # Repositories: index for language filters
    op.create_index("ix_repositories_language", "repositories", ["primary_language"])

    # Saved searches: index for notification queries
    op.create_index("ix_saved_searches_notify", "saved_searches", ["notify"])


def downgrade() -> None:
    op.drop_index("ix_issues_state_repo")
    op.drop_index("ix_issues_updated_at")
    op.drop_index("ix_issues_state_vector")
    op.drop_index("ix_repositories_language")
    op.drop_index("ix_saved_searches_notify")
