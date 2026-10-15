"""Periodic background jobs: expirations, confirmation timeouts, auto-completion, reminders."""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import uow
from app.enums import ListingStatus, OfferStatus
from app.models import Listing, Offer
from app.services import notify
from app.services import orders as orders_svc
from app.timeutil import now

log = logging.getLogger(__name__)


async def expire_listings(session: AsyncSession) -> int:
    q = select(Listing).where(Listing.status == ListingStatus.PUBLISHED, Listing.departure_at <= now())
    n = 0
    for listing in (await session.execute(q)).scalars().all():
        listing.status = ListingStatus.EXPIRED
        listing.closed_at = now()
        n += 1
    return n


async def expire_offers(session: AsyncSession) -> int:
    q = select(Offer).where(Offer.status == OfferStatus.PENDING, Offer.expires_at <= now())
    n = 0
    for offer in (await session.execute(q)).scalars().all():
        offer.status = OfferStatus.EXPIRED
        offer.decided_at = now()
        notify.queue(session, offer.proposed_by_id, "offer.expired", listing_id=offer.listing_id)
        n += 1
    return n


JOBS = [
    orders_svc.timeout_confirmations,
    orders_svc.auto_complete,
    orders_svc.send_reminders,
    expire_offers,
    expire_listings,
]


async def run_once() -> dict[str, int]:
    result = {}
    for job in JOBS:
        try:
            async with uow() as session:
                result[job.__name__] = await job(session)
        except Exception:
            log.exception("job %s failed", job.__name__)
    return result


async def loop(interval: int) -> None:
    while True:
        res = await run_once()
        if any(res.values()):
            log.info("jobs: %s", res)
        await asyncio.sleep(interval)
