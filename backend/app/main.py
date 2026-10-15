import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from app import admin
from app.api.routes import router as api_router
from app.config import settings
from app.db import get_engine, init_engine, uow
from app.services import jobs, locations
from app.services import settings as settings_svc
from app.services.errors import DomainError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

web_templates = Jinja2Templates(directory=str(Path(__file__).parent / "web" / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.debug:
        # refuse to run production with unsafe defaults
        if settings.session_secret in ("", "change-me", "dev-only-secret") or len(settings.session_secret) < 32:
            raise RuntimeError("SESSION_SECRET must be a random string of 32+ characters")
        if settings.bot_mode == "webhook" and len(settings.webhook_secret) < 16:
            raise RuntimeError("WEBHOOK_SECRET must be set (16+ characters) in webhook mode")
    init_engine(settings.database_url)
    async with uow() as s:
        if n := await locations.seed_if_empty(s):
            log.info("seeded %s locations", n)

    bot_runtime = None
    if settings.bot_mode in ("webhook", "polling") and settings.bot_token:
        from app.bot.setup import BotRuntime

        bot_runtime = BotRuntime()
        await bot_runtime.start()
    app.state.bot = bot_runtime

    jobs_task = asyncio.create_task(jobs.loop(settings.jobs_interval_seconds)) if settings.run_jobs else None
    yield
    if jobs_task:
        jobs_task.cancel()
    if bot_runtime:
        await bot_runtime.stop()
    await get_engine().dispose()


app = FastAPI(title="Yo'lchi API", lifespan=lifespan, docs_url="/api/docs" if settings.debug else None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="admin_session",
    same_site="strict",
    https_only=settings.public_url.startswith("https://"),
    max_age=12 * 3600,
)


@app.exception_handler(DomainError)
async def domain_error(request: Request, exc: DomainError):
    return JSONResponse({"error": exc.code, "params": exc.params}, status_code=exc.status)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse({"error": "invalid_input"}, status_code=422)


app.add_exception_handler(admin.AdminRedirect, admin.admin_redirect_handler)
app.include_router(api_router)
app.include_router(admin.router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if request.url.path.startswith("/admin"):
        response.headers.setdefault("X-Frame-Options", "DENY")
    return response


@app.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(request: Request):
    token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not settings.webhook_secret or not secrets.compare_digest(token, settings.webhook_secret):
        return PlainTextResponse("forbidden", status_code=403)
    if request.app.state.bot is None:
        return PlainTextResponse("bot disabled", status_code=503)
    request.app.state.bot.feed(await request.json())
    return PlainTextResponse("ok")


@app.get("/healthz", include_in_schema=False)
async def healthz():
    async with uow() as s:
        await s.execute(text("SELECT 1"))
    return {"ok": True}


@app.get("/terms", response_class=HTMLResponse, include_in_schema=False)
async def terms(request: Request, lang: str = "uz"):
    async with uow() as s:
        cfg = await settings_svc.get_all(s)
    lang = "ru" if lang == "ru" else "uz"
    return web_templates.TemplateResponse(
        request, f"terms_{lang}.html", {"version": cfg["terms_version"], "support": cfg["support_contact"]}
    )


# Telegram Mini App (built React app). index.html must not be cached so new releases load at once.
_dist = Path(settings.miniapp_dist).resolve()
if (_dist / "index.html").exists():
    app.mount("/app/assets", StaticFiles(directory=_dist / "assets"), name="miniapp-assets")

    @app.get("/app", include_in_schema=False)
    async def miniapp_redirect(request: Request):
        return RedirectResponse(f"/app/?{request.url.query}" if request.url.query else "/app/")

    @app.get("/app/", include_in_schema=False)
    async def miniapp_index():
        return FileResponse(_dist / "index.html", headers={"Cache-Control": "no-cache"})
else:
    log.warning("Mini App build not found at %s (run `npm run build` in miniapp/)", _dist)
