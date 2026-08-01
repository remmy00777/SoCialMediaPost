from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Schedule


class CronExpression:
    """Small standard five-field cron evaluator for local scheduling."""

    def __init__(self, expression: str) -> None:
        fields = expression.split()
        if len(fields) != 5:
            raise ValueError("Cron expression must have five fields")
        self.minutes = self._parse(fields[0], 0, 59)
        self.hours = self._parse(fields[1], 0, 23)
        self.days = self._parse(fields[2], 1, 31)
        self.months = self._parse(fields[3], 1, 12)
        self.weekdays = self._parse(fields[4], 0, 7)

    @staticmethod
    def _parse(field: str, minimum: int, maximum: int) -> set[int]:
        values: set[int] = set()
        for component in field.split(','):
            component = component.strip()
            if not component:
                raise ValueError("Empty cron field component")
            base, step_text = (component.split('/', 1) + [None])[:2] if '/' in component else (component, None)
            step = int(step_text) if step_text else 1
            if step <= 0:
                raise ValueError("Cron step must be positive")
            if base == '*':
                start, end = minimum, maximum
            elif '-' in base:
                start_text, end_text = base.split('-', 1)
                start, end = int(start_text), int(end_text)
            else:
                start = end = int(base)
            if start < minimum or end > maximum or start > end:
                raise ValueError("Cron field is out of range")
            values.update(range(start, end + 1, step))
        return values

    def matches(self, value: datetime) -> bool:
        cron_weekday = (value.weekday() + 1) % 7
        weekday_match = cron_weekday in self.weekdays or (cron_weekday == 0 and 7 in self.weekdays)
        return (
            value.minute in self.minutes
            and value.hour in self.hours
            and value.day in self.days
            and value.month in self.months
            and weekday_match
        )

    def next_after(self, value: datetime) -> datetime:
        candidate = value.replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(60 * 24 * 366 * 2):
            if self.matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)
        raise ValueError("No cron occurrence found within two years")


class SchedulerService:
    """Database-backed cron evaluation with one safe catch-up run."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def tick(self, now: datetime | None = None) -> list[str]:
        now_utc = self._as_utc(now or datetime.now(UTC))
        due: list[str] = []
        schedules = self.db.execute(
            select(Schedule).where(Schedule.enabled.is_(True)).with_for_update(skip_locked=True)
        ).scalars().all()
        for schedule in schedules:
            zone = ZoneInfo(schedule.timezone)
            local_now = now_utc.astimezone(zone).replace(second=0, microsecond=0)
            cron = CronExpression(schedule.cron_expression)
            next_run = self._as_utc(schedule.next_run_at) if schedule.next_run_at else None
            if next_run is None:
                if cron.matches(local_now):
                    next_run = now_utc
                else:
                    schedule.next_run_at = self._as_utc(cron.next_after(local_now))
                    continue
            if next_run <= now_utc:
                due.append(schedule.workflow_type)
                schedule.last_run_at = now_utc
                schedule.next_run_at = self._as_utc(cron.next_after(local_now))
        self.db.commit()
        return due

    @staticmethod
    def validate(expression: str, timezone: str) -> None:
        ZoneInfo(timezone)
        CronExpression(expression)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
