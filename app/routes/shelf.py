"""Моя полка и обмены."""
from fastapi import APIRouter, Depends, Request

from app.errors import ValidationFailed
from app.routes.catalog import render_book
from app.routes.deps import get_conn, require_user
from app.services import books, copies, loans
from app.web import flash, form_dict, page_num, redirect, render

router = APIRouter()

_FLASH = {"accept": "Запрос принят. Остальные запросы на этот экземпляр отклонены.",
          "reject": "Запрос отклонён.", "hand-over": "Передача отмечена.",
          "return": "Возврат отмечен — книга снова доступна.", "cancel": "Заявка отменена."}


def render_shelf(request, conn, user, status=200, **extra):
    ctx = {"user": user, "pg": copies.shelf(conn, user["id"], page_num(request)),
           "book_options": [(b["id"], f"{b['title']} — {b['author']}") for b in books.all_books_brief(conn)],
           "values": {}, "errors": {}}
    ctx.update(extra)
    return render(request, "shelf.html", ctx, status)


@router.get("/shelf")
async def shelf_page(request: Request, user=Depends(require_user), conn=Depends(get_conn)):
    values = {"book_id": request.query_params.get("book_id", "")}
    return render_shelf(request, conn, user, values=values)


@router.post("/copies")
async def add_copy(request: Request, user=Depends(require_user), conn=Depends(get_conn)):
    f = await form_dict(request)
    try:
        copies.add_copy(conn, user["id"], f.get("book_id"), f.get("condition"), f.get("pickup_place"))
    except ValidationFailed as e:
        return render_shelf(request, conn, user, 400, values=f, errors=e.fields)
    flash(request, "Экземпляр добавлен на вашу полку.")
    return redirect("/shelf")


@router.get("/copies/{copy_id}/edit")
async def edit_copy_form(copy_id: int, request: Request, user=Depends(require_user), conn=Depends(get_conn)):
    copy = copies.get_owned(conn, copy_id, user)
    return render(request, "copy_form.html", {"user": user, "copy": copy, "values": copy, "errors": {}})


@router.post("/copies/{copy_id}")
async def update_copy(copy_id: int, request: Request, user=Depends(require_user), conn=Depends(get_conn)):
    copy = copies.get_owned(conn, copy_id, user)
    f = await form_dict(request)
    try:
        copies.update_copy(conn, copy_id, user, f.get("condition"), f.get("pickup_place"))
    except ValidationFailed as e:
        return render(request, "copy_form.html", {"user": user, "copy": copy, "values": f, "errors": e.fields}, 400)
    flash(request, "Экземпляр обновлён.")
    return redirect("/shelf")


@router.post("/copies/{copy_id}/visibility")
async def copy_visibility(copy_id: int, request: Request, user=Depends(require_user), conn=Depends(get_conn)):
    f = await form_dict(request)
    show = f.get("show") == "1"
    copies.set_active(conn, copy_id, user, show)
    flash(request, "Экземпляр снова доступен." if show else "Экземпляр скрыт с полки.")
    return redirect("/shelf")


@router.post("/copies/{copy_id}/delete")
async def delete_copy(copy_id: int, request: Request, user=Depends(require_user), conn=Depends(get_conn)):
    copies.delete_copy(conn, copy_id, user)
    flash(request, "Экземпляр удалён.")
    return redirect("/shelf")


@router.post("/copies/{copy_id}/loans")
async def request_loan(copy_id: int, request: Request, user=Depends(require_user), conn=Depends(get_conn)):
    f = await form_dict(request)
    copy = conn.execute("SELECT book_id FROM copies WHERE id = ?", (copy_id,)).fetchone()
    try:
        loans.request_loan(conn, user, copy_id, f.get("requested_return_date"))
    except ValidationFailed as e:
        if copy is None:
            raise
        return render_book(request, conn, user, copy["book_id"], 400,
                           loan_error={"copy_id": copy_id, "message": e.fields.get("requested_return_date", e.message),
                                       "value": f.get("requested_return_date", "")})
    flash(request, "Запрос отправлен владельцу. Следите за статусом в разделе «Обмены».")
    return redirect("/loans?direction=outgoing")


@router.get("/loans")
async def loans_page(request: Request, user=Depends(require_user), conn=Depends(get_conn)):
    direction = request.query_params.get("direction", "incoming")
    if direction not in ("incoming", "outgoing"):
        direction = "incoming"
    flt = request.query_params.get("f", "active")
    if flt not in ("active", "done", "all"):
        flt = "active"
    return render(request, "loans.html", {
        "user": user, "direction": direction, "flt": flt,
        "pg": loans.list_loans(conn, user["id"], direction, flt, page_num(request))})


@router.post("/loans/{loan_id}/{action}")
async def loan_action(loan_id: int, action: str, request: Request, user=Depends(require_user),
                      conn=Depends(get_conn)):
    """accept / reject / hand-over / return / cancel."""
    loans.apply_action(conn, user, loan_id, action)
    flash(request, _FLASH[action])
    f = await form_dict(request)
    direction = f.get("direction", "incoming")
    return redirect(f"/loans?direction={direction if direction in ('incoming', 'outgoing') else 'incoming'}")
