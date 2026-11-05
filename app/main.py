"""Точка входа: uvicorn app.main:app"""
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app import config, db
from app.errors import AppError, NotAuthenticated
from app.routes import admin, auth, catalog, shelf
from app.web import redirect, render

_TITLES = {400: "Некорректный запрос", 401: "Нужно войти", 403: "Доступ запрещён",
           404: "Страница не найдена", 405: "Метод не поддерживается", 409: "Действие невозможно"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = db.connect()
    db.migrate(conn)          # безопасно: уже применённые миграции пропускаются
    conn.close()
    yield


app = FastAPI(title="BookCircle", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, same_site="lax",
                   max_age=14 * 24 * 3600)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")

for module in (auth, catalog, shelf, admin):
    app.include_router(module.router)


def _error_page(request: Request, status: int, message: str):
    return render(request, "error.html", {"code": status, "title": _TITLES.get(status, "Ошибка"),
                                          "message": message}, status)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError):
    return _error_page(request, exc.status, exc.message)


@app.exception_handler(NotAuthenticated)
async def handle_not_authenticated(request: Request, exc: NotAuthenticated):
    target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return redirect(f"/login?next={quote(target)}")


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request: Request, exc: StarletteHTTPException):
    message = "Такой страницы нет." if exc.status_code == 404 else "Запрос не удалось выполнить."
    return _error_page(request, exc.status_code, message)


@app.exception_handler(RequestValidationError)
async def handle_bad_params(request: Request, exc: RequestValidationError):
    return _error_page(request, 404, "Такой страницы или записи нет.")
