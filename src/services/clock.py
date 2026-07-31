from datetime import datetime, timezone


def utcnow() -> datetime:
    """Текущее время в UTC без tzinfo: в БД храним «наивный» UTC (ADR-7)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def time_ago(then: datetime) -> str:
    """«только что», «5 мин назад», «3 ч назад», «вчера», «6 дн назад»."""
    minutes = int((utcnow() - then).total_seconds() // 60)
    if minutes < 1:
        return "только что"
    if minutes < 60:
        return f"{minutes} мин назад"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} ч назад"
    days = hours // 24
    return "вчера" if days == 1 else f"{days} дн назад"
