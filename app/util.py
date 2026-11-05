"""Мелкие помощники: даты, пагинация."""
import math
from dataclasses import dataclass
from datetime import date, datetime


def today() -> date:
    # вынесено в функцию, чтобы в тестах можно было подменить «сегодня»
    return date.today()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_date(value) -> date | None:
    try:
        return date.fromisoformat((value or "").strip())
    except (ValueError, AttributeError):
        return None


def month_bounds(d: date | None = None) -> tuple[str, str]:
    """[начало месяца, начало следующего) в ISO — для статистики по finished_at."""
    d = d or today()
    start = d.replace(day=1)
    end = date(d.year + (1 if d.month == 12 else 0), (d.month % 12) + 1, 1)
    return start.isoformat(), end.isoformat()


@dataclass
class Page:
    items: list
    total: int
    page: int
    per_page: int

    @property
    def pages(self) -> int:
        return max(1, math.ceil(self.total / self.per_page))


def clamp_page(page: int, total: int, per_page: int) -> int:
    pages = max(1, math.ceil(total / per_page))
    return min(max(1, page), pages)


def like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
