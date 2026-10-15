from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ActorType
from app.models import AdminUser, AuditLog


def log_admin(session: AsyncSession, admin: AdminUser, action: str, entity: str, entity_id: int | None, **data) -> None:
    session.add(
        AuditLog(
            actor_type=ActorType.ADMIN,
            actor_id=admin.id,
            actor_name=admin.username,
            action=action,
            entity=entity,
            entity_id=entity_id,
            data=data,
        )
    )


def log_system(session: AsyncSession, action: str, entity: str, entity_id: int | None, **data) -> None:
    session.add(AuditLog(actor_type=ActorType.SYSTEM, action=action, entity=entity, entity_id=entity_id, data=data))
