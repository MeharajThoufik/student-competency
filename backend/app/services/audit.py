from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def audit(db: Session, actor: User, action: str, target_type: str, target_id: int | None, **details: Any) -> None:
    """Add an audit entry to the current transaction (committed with the change it describes)."""
    db.add(AuditLog(actor_id=actor.id, action=action, target_type=target_type, target_id=target_id, details=details))
