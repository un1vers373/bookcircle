"""Ошибки приложения. Каждая несёт HTTP-код и понятное пользователю сообщение."""


class AppError(Exception):
    def __init__(self, status: int, message: str, fields: dict | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.fields = fields or {}


class ValidationFailed(AppError):
    """400: ошибки ввода. fields = {имя_поля: текст_ошибки}."""

    def __init__(self, fields: dict, message: str | None = None):
        if message is None:
            message = "Ошибка в данных: " + "; ".join(fields.values())
        super().__init__(400, message, fields)


class NotAuthenticated(Exception):
    """401: нужно войти (для страниц превращается в редирект на /login)."""


def forbidden(message: str = "Недостаточно прав для этого действия.") -> AppError:
    return AppError(403, message)


def not_found(message: str = "Такой записи не существует.") -> AppError:
    return AppError(404, message)


def conflict(message: str) -> AppError:
    return AppError(409, message)
