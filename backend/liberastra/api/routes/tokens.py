"""API Token 管理：签发、列表、吊销。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.core.security import generate_api_token
from liberastra.models import ApiToken
from liberastra.schemas.token import ApiTokenCreate, ApiTokenCreated, ApiTokenOut

router = APIRouter(prefix="/tokens", tags=["tokens"])


@router.get("", response_model=list[ApiTokenOut])
def list_tokens(user: CurrentUser, db: DbSession) -> list[ApiToken]:
    return list(db.scalars(select(ApiToken).where(ApiToken.owner_id == user.id)).all())


@router.post("", response_model=ApiTokenCreated, status_code=status.HTTP_201_CREATED)
def create_token(body: ApiTokenCreate, user: CurrentUser, db: DbSession) -> ApiTokenCreated:
    plaintext, token_hash, prefix = generate_api_token()
    expires_at = (
        datetime.now(UTC) + timedelta(days=body.expires_in_days) if body.expires_in_days else None
    )
    record = ApiToken(
        name=body.name,
        prefix=prefix,
        token_hash=token_hash,
        scopes=body.scopes,
        owner_id=user.id,
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    data = ApiTokenOut.model_validate(record).model_dump() | {"token": plaintext}
    return ApiTokenCreated(**data)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(token_id: int, user: CurrentUser, db: DbSession) -> None:
    record = db.scalar(
        select(ApiToken).where(ApiToken.id == token_id, ApiToken.owner_id == user.id)
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token 不存在")
    record.revoked = True
    db.commit()
