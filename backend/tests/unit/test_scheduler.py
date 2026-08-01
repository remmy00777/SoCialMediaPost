from datetime import UTC, datetime
from app.core.db import SessionLocal
from app.models import Schedule
from app.services.scheduler import SchedulerService


def test_scheduler_uses_database_cron_and_safe_catchup():
    with SessionLocal() as db:
        db.add(Schedule(name='test', workflow_type='trend_discovery', cron_expression='0 7,13 * * *', timezone='America/Chicago', enabled=True))
        db.commit()
        service = SchedulerService(db)
        due = service.tick(datetime(2026, 7, 30, 12, 0, tzinfo=UTC))  # 7 AM CDT
        assert due == ['trend_discovery']
        assert service.tick(datetime(2026, 7, 30, 12, 0, 30, tzinfo=UTC)) == []


def test_scheduler_validation():
    SchedulerService.validate('0 8,14,20 * * *', 'America/Chicago')
    try:
        SchedulerService.validate('not cron', 'America/Chicago')
    except ValueError:
        pass
    else:
        raise AssertionError('invalid cron should fail')
