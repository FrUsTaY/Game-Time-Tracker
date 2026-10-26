"""
digest.py — еженедельная сводка игровой активности GameTimeTracker.

Модуль намеренно не зависит от Tkinter и базы данных: здесь только чистые
функции, которые легко тестировать (расчёт «пора ли отправлять сводку» и
форматирование текста уведомления).
"""

from datetime import date
from typing import Any, Dict, Optional

from utils import format_duration

#: Период между сводками в днях
DIGEST_PERIOD_DAYS = 7


def parse_iso_date(value: Optional[str]) -> Optional[date]:
    """Разбирает ISO-дату (`YYYY-MM-DD`), возвращая None при ошибке."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def is_weekly_digest_due(last_sent: Optional[str], today: Optional[date] = None,
                         period_days: int = DIGEST_PERIOD_DAYS) -> bool:
    """
    Пора ли отправлять еженедельную сводку.

    Args:
        last_sent: ISO-дата последней отправленной сводки (None — ещё не отправляли).
        today: текущая дата (по умолчанию — сегодня).
        period_days: минимальный интервал между сводками.

    Returns:
        True, если сводку можно отправлять.
    """
    current = today or date.today()
    last_date = parse_iso_date(last_sent)
    if last_date is None:
        return True
    if last_date > current:  # часы «переехали» назад — не спамим
        return False
    return (current - last_date).days >= max(period_days, 1)


def format_weekly_digest(summary: Dict[str, Any]) -> str:
    """
    Формирует текст еженедельной сводки для системного уведомления.

    Args:
        summary: результат `Database.get_weekly_digest()`.

    Returns:
        Готовая строка на русском языке.
    """
    total = int(summary.get('total_seconds') or 0)
    if total <= 0:
        return "За последнюю неделю игровой активности не было"

    parts = [f"За неделю: {format_duration(total)}"]

    delta = int(summary.get('delta_seconds') or 0)
    if delta > 0:
        parts.append(f"на {format_duration(delta)} больше, чем на прошлой")
    elif delta < 0:
        parts.append(f"на {format_duration(-delta)} меньше, чем на прошлой")

    message = parts[0]
    if len(parts) > 1:
        message += f" ({parts[1]})"

    top_game = str(summary.get('top_game') or "").strip()
    if top_game:
        message += f". Топ: {top_game} — {format_duration(int(summary.get('top_game_seconds') or 0))}"

    active_days = int(summary.get('active_days') or 0)
    message += f". Активных дней: {active_days} из {DIGEST_PERIOD_DAYS}"

    streak = int(summary.get('streak') or 0)
    if streak > 1:
        message += f", серия: {streak} дн. подряд"

    return message
