import math


DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


def normalize_pagination(page: int | None, per_page: int | None) -> tuple[int, int, int]:
    page = page or DEFAULT_PAGE
    per_page = per_page or DEFAULT_PER_PAGE
    if page < 1:
        page = DEFAULT_PAGE
    if per_page < 1:
        per_page = DEFAULT_PER_PAGE
    if per_page > MAX_PER_PAGE:
        per_page = MAX_PER_PAGE
    offset = (page - 1) * per_page
    return page, per_page, offset


def build_pagination_meta(*, total: int, page: int, per_page: int) -> dict:
    pages = math.ceil(total / per_page) if total else 0
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }
