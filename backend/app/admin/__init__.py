"""Web admin panel (TZ §17): verification, users, listings, orders, complaints, reviews, settings, audit."""

import secrets
import time
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.db import uow
from app.enums import AdminRole, CarrierStatus, Category, ComplaintStatus, ListingStatus, OrderStatus
from app.i18n import money, t
from app.models import (
    AdminUser,
    AuditLog,
    Cancellation,
    CarrierProfile,
    Complaint,
    Document,
    Listing,
    Offer,
    Order,
    Review,
    StoredFile,
    User,
)
from app.security import verify_password
from app.services import carriers, listings, orders, reviews, stats, users
from app.services import files as files_svc
from app.services import settings as settings_svc
from app.services.errors import DomainError
from app.timeutil import fmt, now

router = APIRouter(prefix="/admin", include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["dt"] = fmt
templates.env.filters["money"] = money
templates.env.globals["cat"] = lambda c: t("uz", f"cat.{c}")
templates.env.globals["reason"] = lambda c: t("uz", f"reason.{c}")

R = AdminRole
ALL = {R.SUPERADMIN, R.MODERATOR, R.SUPPORT}
ACCESS = {
    "dashboard": ALL,
    "verifications": {R.SUPERADMIN, R.MODERATOR},
    "users": ALL,
    "listings": ALL,
    "orders": {R.SUPERADMIN, R.SUPPORT},
    "complaints": {R.SUPERADMIN, R.SUPPORT},
    "reviews": {R.SUPERADMIN, R.MODERATOR},
    "settings": {R.SUPERADMIN},
    "audit": {R.SUPERADMIN},
}
NAV = [
    ("dashboard", "/admin/", "Statistika"),
    ("verifications", "/admin/verifications", "Tekshiruv"),
    ("users", "/admin/users", "Foydalanuvchilar"),
    ("listings", "/admin/listings", "E'lonlar"),
    ("orders", "/admin/orders", "Buyurtmalar"),
    ("complaints", "/admin/complaints", "Shikoyatlar"),
    ("reviews", "/admin/reviews", "Sharhlar"),
    ("settings", "/admin/settings", "Sozlamalar"),
    ("audit", "/admin/audit", "Audit"),
]
PAGE = 50

_login_attempts: dict[str, list[float]] = defaultdict(list)


class AdminRedirect(Exception):
    def __init__(self, url: str):
        self.url = url


async def admin_redirect_handler(request: Request, exc: AdminRedirect):
    return RedirectResponse(exc.url, status_code=303)


async def _auth(request: Request, s, page: str) -> AdminUser:
    admin_id = request.session.get("admin_id")
    admin = await s.get(AdminUser, admin_id) if admin_id else None
    if admin is None or not admin.is_active:
        request.session.clear()
        raise AdminRedirect("/admin/login")
    if admin.role not in ACCESS[page]:
        flash(request, "Bu bo'limga ruxsat yo'q")
        raise AdminRedirect("/admin/")
    return admin


def _csrf(request: Request) -> str:
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_urlsafe(24)
    return request.session["csrf"]


async def _form(request: Request) -> dict:
    form = await request.form()
    if not secrets.compare_digest(str(form.get("csrf", "")), request.session.get("csrf", "-")):
        raise AdminRedirect(request.headers.get("referer") or "/admin/")
    return form


def flash(request: Request, msg: str) -> None:
    request.session["flash"] = msg


def render(request: Request, name: str, admin: AdminUser | None, **ctx) -> HTMLResponse:
    nav = [(k, url, label) for k, url, label in NAV if admin and admin.role in ACCESS[k]]
    return templates.TemplateResponse(
        request,
        name,
        {"admin": admin, "nav": nav, "csrf": _csrf(request), "flash": request.session.pop("flash", None), **ctx},
    )


def back(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


async def _act(request: Request, url: str, coro_fn, ok: str) -> RedirectResponse:
    """Runs an admin action; turns domain errors into a flash message."""
    try:
        await coro_fn()
        flash(request, ok)
    except DomainError as e:
        flash(request, f"Xatolik: {e.code}")
    return back(url)


# ------------------------------------------------------------------ auth


@router.get("/login")
async def login_page(request: Request):
    return render(request, "login.html", None)


@router.post("/login")
async def login(request: Request):
    ip = request.client.host if request.client else "?"
    attempts = [x for x in _login_attempts[ip] if x > time.time() - 900]
    _login_attempts[ip] = attempts
    if len(attempts) >= 5:
        flash(request, "Juda ko'p urinish. 15 daqiqadan keyin qayta urinib ko'ring.")
        return back("/admin/login")
    form = await _form(request)
    async with uow() as s:
        admin = (await s.execute(select(AdminUser).where(AdminUser.username == str(form.get("username", ""))))).scalar_one_or_none()
        if admin is None or not admin.is_active or not verify_password(str(form.get("password", "")), admin.password_hash):
            attempts.append(time.time())
            flash(request, "Login yoki parol noto'g'ri")
            return back("/admin/login")
        admin.last_login_at = now()
        request.session.clear()
        request.session["admin_id"] = admin.id
    return back("/admin/")


@router.post("/logout")
async def logout(request: Request):
    await _form(request)
    request.session.clear()
    return back("/admin/login")


# ------------------------------------------------------------------ dashboard


@router.get("/")
async def dashboard(request: Request):
    async with uow() as s:
        admin = await _auth(request, s, "dashboard")
        data = await stats.dashboard(s)
    return render(request, "dashboard.html", admin, s=data)


# ------------------------------------------------------------------ verification


@router.get("/verifications")
async def verifications(request: Request, status: str = CarrierStatus.PENDING):
    async with uow() as s:
        admin = await _auth(request, s, "verifications")
        rows = (
            await s.execute(
                select(CarrierProfile)
                .options(selectinload(CarrierProfile.user))
                .where(CarrierProfile.status == status)
                .order_by(CarrierProfile.submitted_at.asc())
                .limit(200)
            )
        ).scalars().all()
    return render(request, "verifications.html", admin, rows=rows, status=status, statuses=list(CarrierStatus))


@router.get("/verifications/{profile_id}")
async def verification(request: Request, profile_id: int):
    async with uow() as s:
        admin = await _auth(request, s, "verifications")
        profile = (
            await s.execute(select(CarrierProfile).options(selectinload(CarrierProfile.user)).where(CarrierProfile.id == profile_id))
        ).scalar_one_or_none()
        if profile is None:
            return back("/admin/verifications")
        ctx = dict(
            p=profile,
            docs=await carriers.documents(s, profile.user_id),
            vehicles=await carriers.vehicles(s, profile.user),
            perms=await carriers.permissions(s, profile.user_id),
            categories=list(Category),
            enabled=await settings_svc.get(s, "enabled_categories"),
            files={f.id: f for f in (await s.execute(
                select(StoredFile).join(Document, Document.file_id == StoredFile.id).where(Document.user_id == profile.user_id)
            )).scalars()},
        )
    return render(request, "verification.html", admin, **ctx)


@router.post("/verifications/{profile_id}/{action}")
async def verification_action(request: Request, profile_id: int, action: str):
    form = await _form(request)
    url = f"/admin/verifications/{profile_id}"
    reason = str(form.get("reason", ""))

    async def run():
        async with uow() as s:
            admin = await _auth(request, s, "verifications")
            if action == "approve":
                await carriers.approve(s, profile_id, form.getlist("categories"), admin)
            elif action in ("reject", "resubmit"):
                await carriers.reject(s, profile_id, reason, admin, resubmit=action == "resubmit")
            elif action == "revoke":
                await carriers.revoke(s, profile_id, reason, admin)
            else:
                raise DomainError("not_found")

    return await _act(request, url, run, "Saqlandi")


@router.get("/files/{file_id}")
async def admin_file(request: Request, file_id: int):
    async with uow() as s:
        await _auth(request, s, "dashboard")
        f = await s.get(StoredFile, file_id)
        if f is None:
            return HTMLResponse("not found", status_code=404)
        path = files_svc.full_path(f)
    return FileResponse(path, media_type=f.mime, headers={"Cache-Control": "private, no-store"})


# ------------------------------------------------------------------ users


@router.get("/users")
async def users_page(request: Request, q: str = "", page: int = 0):
    async with uow() as s:
        admin = await _auth(request, s, "users")
        query = select(User).order_by(User.id.desc()).limit(PAGE).offset(page * PAGE)
        if q:
            like = f"%{q.strip()}%"
            cond = [User.phone.ilike(like), User.first_name.ilike(like), User.username.ilike(like)]
            if q.strip().isdigit():
                cond += [User.id == int(q), User.telegram_id == int(q)]
            query = query.where(or_(*cond))
        rows = (await s.execute(query)).scalars().all()
    return render(request, "users.html", admin, rows=rows, q=q, page=page)


@router.get("/users/{user_id}")
async def user_page(request: Request, user_id: int):
    async with uow() as s:
        admin = await _auth(request, s, "users")
        u = await s.get(User, user_id)
        if u is None:
            return back("/admin/users")
        profile = (await s.execute(select(CarrierProfile).where(CarrierProfile.user_id == u.id))).scalar_one_or_none()
        user_listings = (await s.execute(
            select(Listing).options(selectinload(Listing.from_location), selectinload(Listing.to_location))
            .where(Listing.author_id == u.id).order_by(Listing.id.desc()).limit(50)
        )).scalars().all()
        user_orders = (await s.execute(
            select(Order).options(selectinload(Order.from_location), selectinload(Order.to_location))
            .where(or_(Order.client_id == u.id, Order.carrier_id == u.id)).order_by(Order.id.desc()).limit(50)
        )).scalars().all()
        complaints_n = await s.scalar(select(func.count(Complaint.id)).join(Order).where(
            or_(Order.client_id == u.id, Order.carrier_id == u.id)))
    return render(request, "user.html", admin, u=u, profile=profile, listings=user_listings,
                  orders=user_orders, complaints_n=complaints_n)


@router.post("/users/{user_id}/{action}")
async def user_action(request: Request, user_id: int, action: str):
    form = await _form(request)

    async def run():
        async with uow() as s:
            admin = await _auth(request, s, "users")
            u = await s.get(User, user_id)
            if u is None or action not in ("block", "unblock"):
                raise DomainError("not_found")
            if action == "block":
                users.block(s, u, str(form.get("reason", "")), admin)
            else:
                users.unblock(s, u, admin)

    return await _act(request, f"/admin/users/{user_id}", run, "Saqlandi")


# ------------------------------------------------------------------ listings


@router.get("/listings")
async def listings_page(request: Request, status: str = ListingStatus.PUBLISHED, page: int = 0):
    async with uow() as s:
        admin = await _auth(request, s, "listings")
        q = select(Listing).options(*listings.load_options()).order_by(Listing.id.desc()).limit(PAGE).offset(page * PAGE)
        if status:
            q = q.where(Listing.status == status)
        rows = (await s.execute(q)).scalars().all()
    return render(request, "listings.html", admin, rows=rows, status=status, statuses=list(ListingStatus), page=page)


@router.get("/listings/{listing_id}")
async def listing_page(request: Request, listing_id: int):
    async with uow() as s:
        admin = await _auth(request, s, "listings")
        try:
            l = await listings.get(s, listing_id)
        except DomainError:
            return back("/admin/listings")
        offer_rows = (await s.execute(
            select(Offer).options(selectinload(Offer.counterparty)).where(Offer.listing_id == l.id).order_by(Offer.id)
        )).scalars().all()
        order_rows = (await s.execute(select(Order).where(Order.listing_id == l.id).order_by(Order.id))).scalars().all()
    return render(request, "listing.html", admin, l=l, offers=offer_rows, orders=order_rows)


@router.post("/listings/{listing_id}/cancel")
async def listing_cancel(request: Request, listing_id: int):
    form = await _form(request)

    async def run():
        async with uow() as s:
            admin = await _auth(request, s, "listings")
            reason = str(form.get("reason", "")).strip()
            if not reason:
                raise DomainError("reason_required")
            await listings.admin_cancel(s, listing_id, reason, admin)

    return await _act(request, f"/admin/listings/{listing_id}", run, "E'lon olib tashlandi")


# ------------------------------------------------------------------ orders & complaints


@router.get("/orders")
async def orders_page(request: Request, status: str = "", q: str = "", page: int = 0):
    async with uow() as s:
        admin = await _auth(request, s, "orders")
        query = (
            select(Order)
            .options(selectinload(Order.client), selectinload(Order.carrier),
                     selectinload(Order.from_location), selectinload(Order.to_location))
            .order_by(Order.id.desc()).limit(PAGE).offset(page * PAGE)
        )
        if status:
            query = query.where(Order.status == status)
        if q.strip().isdigit():
            query = query.where(Order.id == int(q))
        rows = (await s.execute(query)).scalars().all()
    return render(request, "orders.html", admin, rows=rows, status=status, statuses=list(OrderStatus), q=q, page=page)


@router.get("/orders/{order_id}")
async def order_page(request: Request, order_id: int):
    async with uow() as s:
        admin = await _auth(request, s, "orders")
        try:
            o = await orders.get(s, order_id)
        except DomainError:
            return back("/admin/orders")
        ctx = dict(
            o=o,
            history=await orders.history(s, o.id),
            cancellations=(await s.execute(select(Cancellation).where(Cancellation.order_id == o.id))).scalars().all(),
            complaints=(await s.execute(
                select(Complaint).options(selectinload(Complaint.author)).where(Complaint.order_id == o.id).order_by(Complaint.id)
            )).scalars().all(),
            reviews=await reviews.for_order(s, o.id),
            offer_chain=await _offer_chain(s, o.offer_id),
            code_max_attempts=orders.DELIVERY_CODE_MAX_ATTEMPTS,
        )
    return render(request, "order.html", admin, **ctx)


async def _offer_chain(s, offer_id: int) -> list[Offer]:
    chain = []
    current = await s.get(Offer, offer_id)
    while current is not None and len(chain) < 50:
        chain.append(current)
        current = await s.get(Offer, current.parent_id) if current.parent_id else None
    return list(reversed(chain))


@router.get("/complaints")
async def complaints_page(request: Request, status: str = ComplaintStatus.OPEN):
    async with uow() as s:
        admin = await _auth(request, s, "complaints")
        rows = (await s.execute(
            select(Complaint).options(selectinload(Complaint.author), selectinload(Complaint.order))
            .where(Complaint.status == status).order_by(Complaint.id.desc()).limit(200)
        )).scalars().all()
    return render(request, "complaints.html", admin, rows=rows, status=status)


@router.post("/complaints/{complaint_id}/resolve")
async def complaint_resolve(request: Request, complaint_id: int):
    form = await _form(request)
    order_id = int(form.get("order_id", 0))

    async def run():
        async with uow() as s:
            admin = await _auth(request, s, "complaints")
            await orders.resolve_complaint(s, complaint_id, str(form.get("outcome", "")), str(form.get("resolution", "")), admin)

    return await _act(request, f"/admin/orders/{order_id}", run, "Qaror saqlandi")


# ------------------------------------------------------------------ reviews


@router.get("/reviews")
async def reviews_page(request: Request, page: int = 0):
    async with uow() as s:
        admin = await _auth(request, s, "reviews")
        rows = (await s.execute(
            select(Review).options(selectinload(Review.author), selectinload(Review.target))
            .order_by(Review.id.desc()).limit(PAGE).offset(page * PAGE)
        )).scalars().all()
    return render(request, "reviews.html", admin, rows=rows, page=page)


@router.post("/reviews/{review_id}/{action}")
async def review_action(request: Request, review_id: int, action: str):
    form = await _form(request)

    async def run():
        async with uow() as s:
            admin = await _auth(request, s, "reviews")
            await reviews.set_hidden(s, review_id, action == "hide", str(form.get("reason", "")), admin)

    return await _act(request, "/admin/reviews", run, "Saqlandi")


# ------------------------------------------------------------------ settings & audit

SETTING_LABELS = {
    "commission_percent": "Komissiya, % (pilotda faqat statistika uchun hisoblanadi)",
    "offer_ttl_minutes": "Taklif amal qilish muddati, daqiqa",
    "confirm_timeout_minutes": "Tashuvchi tasdiqlashi uchun vaqt, daqiqa",
    "auto_complete_hours": "Avtomatik yakunlash, soat",
    "reminder_before_minutes": "Jo'nashdan oldin eslatma, daqiqa",
    "late_cancel_hours": "Kech bekor qilish chegarasi, soat",
    "enabled_categories": "Yoqilgan toifalar (vergul bilan)",
    "required_documents": "Majburiy hujjatlar (vergul bilan)",
    "max_active_listings": "Bir foydalanuvchining faol e'lonlari limiti",
    "max_subscriptions": "Obunalar limiti",
    "terms_version": "Oferta versiyasi",
    "support_contact": "Yordam kontakti",
    "price_per_km_passenger": "Narx maslahati: yo'lovchi, so'm/km (1 o'rindiq)",
    "price_per_km_parcel": "Narx maslahati: posilka, so'm/km",
}


@router.get("/settings")
async def settings_page(request: Request):
    async with uow() as s:
        admin = await _auth(request, s, "settings")
        values = await settings_svc.get_all(s)
    shown = {k: ",".join(v) if isinstance(v, list) else v for k, v in values.items()}
    return render(request, "settings.html", admin, values=shown, labels=SETTING_LABELS)


@router.post("/settings")
async def settings_save(request: Request):
    form = await _form(request)

    async def run():
        async with uow() as s:
            admin = await _auth(request, s, "settings")
            for key in SETTING_LABELS:
                if key in form:
                    await settings_svc.set_value(s, key, str(form[key]), admin)

    return await _act(request, "/admin/settings", run, "Sozlamalar saqlandi")


@router.get("/audit")
async def audit_page(request: Request, page: int = 0):
    async with uow() as s:
        admin = await _auth(request, s, "audit")
        rows = (await s.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(PAGE).offset(page * PAGE))).scalars().all()
    return render(request, "audit.html", admin, rows=rows, page=page)
