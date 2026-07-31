from datetime import datetime, timezone


def utcnow() -> datetime:
    """Текущее время в UTC без tzinfo: в БД храним «наивный» UTC (ADR-7)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
