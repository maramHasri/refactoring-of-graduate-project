"""Background job: auto-publish SCHEDULED tests when scheduled_publish_at is reached."""
from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)

_stop_event = threading.Event()
_thread: threading.Thread | None = None


def _publish_due_tests(app) -> list[int]:
    with app.app_context():
        from service.test_service import TestService

        return TestService().publish_due_scheduled_tests()


def _run_loop(app, interval: int) -> None:
    first_run = True
    while not _stop_event.is_set():
        if not first_run and _stop_event.wait(interval):
            break
        first_run = False

        try:
            published_ids = _publish_due_tests(app)
            if published_ids:
                logger.info(
                    "Auto-published %s scheduled test(s): %s",
                    len(published_ids),
                    published_ids,
                )
        except Exception:
            logger.exception("Scheduled test publish job failed")


def init_scheduled_test_publisher(app) -> None:
    global _thread

    if not app.config.get("SCHEDULED_TEST_PUBLISH_ENABLED", True):
        return
    if app.config.get("TESTING"):
        return
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    if _thread and _thread.is_alive():
        return

    interval = int(app.config.get("SCHEDULED_TEST_PUBLISH_INTERVAL_SECONDS", 60))
    _stop_event.clear()
    _thread = threading.Thread(
        target=_run_loop,
        args=(app, interval),
        name="scheduled-test-publisher",
        daemon=True,
    )
    _thread.start()
    logger.info("Scheduled test publisher started (interval=%ss)", interval)
