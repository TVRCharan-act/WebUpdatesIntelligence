"""Continuously dispatch due monitors for the local Compose stack.

Production invokes the same selection logic from EventBridge once a minute.
Compose has no EventBridge target, so this small process supplies that missing
tick while keeping the actual monitor work in the normal local job runner.
"""

from __future__ import annotations

import logging
from time import sleep

from backend.app.auth import bootstrap_accounts
from backend.app.config import get_settings
from backend.app.repository import get_repository
from backend.app.services.ecs import JobDispatcher
from backend.app.services.scheduling import dispatch_due_monitors


logger = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 15


def dispatch_once() -> dict:
    """Run one safe due-monitor selection pass."""
    repository = get_repository()
    bootstrap_accounts(repository)
    return dispatch_due_monitors(repository, JobDispatcher(repository))


def main() -> None:
    settings = get_settings()
    settings.require_storage()
    if settings.require_task_execution_backend() != "local":
        logger.info("Local scheduler disabled because task execution uses ECS.")
        return

    logger.info("Local monitor scheduler started; polling every %s seconds.", POLL_INTERVAL_SECONDS)
    while True:
        try:
            result = dispatch_once()
            if result["queued_source_ids"] or result["failures"]:
                logger.info("Local scheduler pass: %s", result)
        except Exception:
            # A transient storage or provider issue must not permanently stop
            # automatic checks for every customer in this development stack.
            logger.exception("Local scheduler pass failed.")
        sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
