"""Помощники веб-слоя: шаблоны, flash-сообщения, пагинация, редиректы."""
from urllib.parse import urlencode

from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import config, db, filters
from app.services import users

templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


filters.install(templates.env)


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def safe_next(value, default: str) -> str:
    """Разрешаем редирект только на внутренние адреса."""
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return default


def flash(request, text: str, kind: str = "ok"):
    request.session["flash"] = {"text": text, "kind": kind}


def page_num(request) -> int:
    try:
        return max(1, int(request.query_params.get("page", 1)))
    except ValueError:
        return 1


def _page_url(request, n: int) -> str:
    params = dict(request.query_params)
    params["page"] = n
    return f"{request.url.path}?{urlencode(params)}"


async def form_dict(request) -> dict:
    form = await request.form()
    return {k: v for k, v in form.items() if isinstance(v, str)}


def _load_user(request):
    uid = request.session.get("uid")
    if not uid:
        return None
    conn = db.connect()
    try:
        return users.get_user(conn, uid)
    finally:
        conn.close()


def render(request, name: str, ctx: dict | None = None, status: int = 200):
    ctx = dict(ctx or {})
    if "user" not in ctx:
        ctx["user"] = _load_user(request)
    ctx["flash"] = request.session.pop("flash", None)
    ctx["page_url"] = lambda n: _page_url(request, n)
    ctx["current_path"] = request.url.path
    return templates.TemplateResponse(request, name, ctx, status_code=status)
