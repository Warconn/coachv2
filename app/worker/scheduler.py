from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app import create_app

from .tasks import run_ingest_cycle

logger = logging.getLogger(__name__)


def register_cron_job(
    scheduler: BlockingScheduler, cron_expr: str, job_id: str, app_context_arg
) -> None:
    try:
        trigger = CronTrigger.from_crontab(cron_expr, timezone=app_context_arg.config["TIMEZONE"])
    except ValueError as exc:
        logger.error("Invalid cron expression '%s': %s", cron_expr, exc)
        return

    scheduler.add_job(
        func=run_ingest_cycle,
        trigger=trigger,
        id=job_id,
        replace_existing=True,
        args=[app_context_arg],
    )
    logger.info("Scheduled job '%s' with cron '%s'", job_id, cron_expr)


def main() -> None:
    app = create_app()
    scheduler = BlockingScheduler(timezone=app.config["TIMEZONE"])

    register_cron_job(scheduler, app.config["INGEST_CRON_MORNING"], "ingest-morning", app)
    register_cron_job(scheduler, app.config["INGEST_CRON_EVENING"], "ingest-evening", app)

    logger.info("CoachV2 scheduler started with timezone %s", app.config["TIMEZONE"])

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutdown requested")


if __name__ == "__main__":
    main()

