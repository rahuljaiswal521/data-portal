"""Git operations via GitPython — auto-commit YAML changes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class GitService:
    def __init__(self) -> None:
        self._repo = None
        if settings.git_enabled:
            try:
                import git
                repo_path = Path(settings.framework_root)
                self._repo = git.Repo(repo_path, search_parent_directories=True)
            except Exception as e:
                logger.warning("Git not available: %s", e)

    @property
    def available(self) -> bool:
        return self._repo is not None

    def commit_file(self, file_path: str, message: str) -> Optional[str]:
        if not self.available:
            logger.info("Git not available, skipping commit")
            return None

        try:
            rel_path = Path(file_path).relative_to(self._repo.working_dir)
            self._repo.index.add([str(rel_path)])
            commit = self._repo.index.commit(message)
            sha = commit.hexsha[:8]
            logger.info("Committed %s: %s", sha, message)

            if settings.git_auto_push:
                self._repo.remote("origin").push()
                logger.info("Pushed to origin")

            return sha
        except Exception as e:
            logger.error("Git commit failed: %s", e)
            return None

    def commit_delete(self, file_path: str, message: str) -> Optional[str]:
        if not self.available:
            return None

        try:
            rel_path = Path(file_path).relative_to(self._repo.working_dir)
            self._repo.index.remove([str(rel_path)], working_tree=True)
            commit = self._repo.index.commit(message)
            sha = commit.hexsha[:8]
            logger.info("Committed delete %s: %s", sha, message)
            return sha
        except Exception as e:
            logger.error("Git delete commit failed: %s", e)
            return None
