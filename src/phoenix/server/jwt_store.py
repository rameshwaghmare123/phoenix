import logging
from abc import ABC, abstractmethod
from asyncio import create_task, gather, sleep
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from functools import cached_property
from typing import Any, Callable, Dict, Generic, List, Optional, Tuple, Type, TypeVar

import jwt
from sqlalchemy import Select, delete, select

from phoenix.auth import (
    JWT_ALGORITHM,
    ClaimSet,
    Token,
)
from phoenix.db import models
from phoenix.db.enums import UserRole
from phoenix.server.types import (
    AccessToken,
    AccessTokenAttributes,
    AccessTokenClaims,
    AccessTokenId,
    ApiKey,
    ApiKeyAttributes,
    ApiKeyClaims,
    ApiKeyId,
    DaemonTask,
    DbSessionFactory,
    RefreshToken,
    RefreshTokenAttributes,
    RefreshTokenClaims,
    RefreshTokenId,
    TokenId,
    UserId,
)

logger = logging.getLogger(__name__)


class JwtStore:
    def __init__(
        self,
        db: DbSessionFactory,
        secret: str,
        algorithm: str = JWT_ALGORITHM,
        sleep_seconds: int = 10,
        **kwargs: Any,
    ) -> None:
        assert secret
        super().__init__(**kwargs)
        self._secret = secret
        args = (db, secret, algorithm, sleep_seconds)
        self._access_token_store = AccessTokenStore(*args, **kwargs)
        self._refresh_token_store = RefreshTokenStore(*args, **kwargs)
        self._api_key_store = ApiKeyStore(*args, **kwargs)

    @cached_property
    def _stores(self) -> Tuple[DaemonTask, ...]:
        return tuple(dt for dt in self.__dict__.values() if isinstance(dt, _Store))

    async def __aenter__(self) -> None:
        await gather(*(s.__aenter__() for s in self._stores))

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await gather(*(s.__aexit__(*args, **kwargs) for s in self._stores))

    async def read(self, token: Token) -> Optional[ClaimSet]:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[JWT_ALGORITHM],
                options={"verify_exp": False},
            )
        except jwt.DecodeError:
            return None
        if (jti := payload.get("jti")) is None:
            return None
        if (token_id := TokenId.parse(jti)) is None:
            return None
        if isinstance(token_id, AccessTokenId):
            return await self._access_token_store.get(token_id)
        if isinstance(token_id, RefreshTokenId):
            return await self._refresh_token_store.get(token_id)
        if isinstance(token_id, ApiKeyId):
            return await self._api_key_store.get(token_id)
        return None

    async def create_access_token(
        self,
        claim: AccessTokenClaims,
    ) -> Tuple[AccessToken, AccessTokenId]:
        return await self._access_token_store.create(claim)

    async def create_refresh_token(
        self,
        claim: RefreshTokenClaims,
    ) -> Tuple[RefreshToken, RefreshTokenId]:
        return await self._refresh_token_store.create(claim)

    async def create_api_key(
        self,
        claim: ApiKeyClaims,
    ) -> Tuple[ApiKey, ApiKeyId]:
        return await self._api_key_store.create(claim)

    async def revoke(self, *token_ids: TokenId) -> None:
        if not token_ids:
            return
        access_token_ids: List[AccessTokenId] = []
        refresh_token_ids: List[RefreshTokenId] = []
        api_key_ids: List[ApiKeyId] = []
        for token_id in token_ids:
            if isinstance(token_id, AccessTokenId):
                access_token_ids.append(token_id)
            elif isinstance(token_id, RefreshTokenId):
                refresh_token_ids.append(token_id)
            elif isinstance(token_id, ApiKeyId):
                api_key_ids.append(token_id)
        await gather(
            self._access_token_store.revoke(*access_token_ids),
            self._refresh_token_store.revoke(*refresh_token_ids),
            self._api_key_store.revoke(*api_key_ids),
        )


_TokenT = TypeVar("_TokenT", bound=Token)
_TokenIdT = TypeVar("_TokenIdT", bound=TokenId)
_ClaimSetT = TypeVar("_ClaimSetT", bound=ClaimSet)
_TokenTableT = TypeVar("_TokenTableT", models.AccessToken, models.RefreshToken, models.ApiKey)


class _Claims(Generic[_TokenIdT, _ClaimSetT]):
    def __init__(self) -> None:
        self._cache: Dict[_TokenIdT, _ClaimSetT] = {}

    def __getitem__(self, token_id: _TokenIdT) -> Optional[_ClaimSetT]:
        claim = self._cache.get(token_id)
        return deepcopy(claim) if claim else None

    def __setitem__(self, token_id: _TokenIdT, claim: _ClaimSetT) -> None:
        self._cache[token_id] = deepcopy(claim)

    def get(self, token_id: _TokenIdT) -> Optional[_ClaimSetT]:
        claim = self._cache.get(token_id)
        return deepcopy(claim) if claim else None

    def pop(
        self, token_id: _TokenIdT, default: Optional[_ClaimSetT] = None
    ) -> Optional[_ClaimSetT]:
        claim = self._cache.pop(token_id, default)
        return deepcopy(claim) if claim else None


class _Store(DaemonTask, Generic[_ClaimSetT, _TokenT, _TokenIdT, _TokenTableT], ABC):
    _table: Type[_TokenTableT]
    _token_id: Callable[[int], _TokenIdT]
    _token: Callable[[str], _TokenT]

    def __init__(
        self,
        db: DbSessionFactory,
        secret: str,
        algorithm: str = JWT_ALGORITHM,
        sleep_seconds: int = 10,
        **kwargs: Any,
    ) -> None:
        assert secret
        super().__init__(**kwargs)
        self._db = db
        self._seconds = sleep_seconds
        self._claims: _Claims[_TokenIdT, _ClaimSetT] = _Claims()
        self._secret = secret
        self._algorithm = algorithm

    def _encode(self, claim: ClaimSet) -> str:
        payload: Dict[str, Any] = dict(jti=claim.token_id)
        if claim.expiration_time:
            payload["exp"] = int(claim.expiration_time.timestamp())
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    async def get(self, token_id: _TokenIdT) -> Optional[_ClaimSetT]:
        return self._claims.get(token_id)

    async def revoke(self, *token_ids: _TokenIdT) -> None:
        if not token_ids:
            return
        for token_id in token_ids:
            self._claims.pop(token_id, None)
        stmt = delete(self._table).where(self._table.id.in_(map(int, token_ids)))
        async with self._db() as session:
            await session.execute(stmt)

    @abstractmethod
    def _from_db(self, record: _TokenTableT, role: UserRole) -> Tuple[_TokenIdT, _ClaimSetT]: ...

    @abstractmethod
    def _to_db(self, claims: _ClaimSetT) -> _TokenTableT: ...

    async def create(self, claim: _ClaimSetT) -> Tuple[_TokenT, _TokenIdT]:
        record = self._to_db(claim)
        async with self._db() as session:
            session.add(record)
            await session.flush()
        token_id = self._token_id(record.id)
        claim = replace(claim, token_id=token_id)
        self._claims[token_id] = claim
        return self._token(self._encode(claim)), token_id

    async def _update(self) -> None:
        claims: _Claims[_TokenIdT, _ClaimSetT] = _Claims()
        async with self._db() as session:
            async with session.begin_nested():
                await self._delete_expired_tokens(session)
            async with session.begin_nested():
                async for token_record, user_role in await session.stream(self._update_stmt):
                    token_id, claim_set = self._from_db(token_record, UserRole(user_role))
                    claims[token_id] = claim_set
        self._claims = claims

    @cached_property
    def _update_stmt(self) -> Select[Tuple[_TokenTableT, str]]:
        return (
            select(self._table, models.UserRole.name)
            .join_from(self._table, models.User)
            .join_from(models.User, models.UserRole)
        )

    async def _delete_expired_tokens(self, session: Any) -> None:
        now = datetime.now(timezone.utc)
        await session.execute(delete(self._table).where(self._table.expires_at < now))

    async def _run(self) -> None:
        while self._running:
            self._tasks.append(create_task(self._update()))
            await self._tasks[-1]
            self._tasks.pop()
            self._tasks.append(create_task(sleep(self._seconds)))
            await self._tasks[-1]
            self._tasks.pop()


class AccessTokenStore(
    _Store[
        AccessTokenClaims,
        AccessToken,
        AccessTokenId,
        models.AccessToken,
    ]
):
    _table = models.AccessToken
    _token_id = AccessTokenId
    _token = AccessToken

    def _from_db(
        self,
        record: models.AccessToken,
        user_role: UserRole,
    ) -> Tuple[AccessTokenId, AccessTokenClaims]:
        token_id = AccessTokenId(record.id)
        refresh_token_id = RefreshTokenId(record.refresh_token_id)
        return token_id, AccessTokenClaims(
            token_id=token_id,
            subject=UserId(record.user_id),
            issued_at=record.created_at,
            expiration_time=record.expires_at,
            attributes=AccessTokenAttributes(
                user_role=user_role,
                refresh_token_id=refresh_token_id,
            ),
        )

    def _to_db(self, claim: AccessTokenClaims) -> models.AccessToken:
        assert claim.expiration_time
        assert claim.subject
        user_id = int(claim.subject)
        assert claim.attributes
        refresh_token_id = int(claim.attributes.refresh_token_id)
        return models.AccessToken(
            user_id=user_id,
            created_at=claim.issued_at,
            expires_at=claim.expiration_time,
            refresh_token_id=refresh_token_id,
        )


class RefreshTokenStore(
    _Store[
        RefreshTokenClaims,
        RefreshToken,
        RefreshTokenId,
        models.RefreshToken,
    ]
):
    _table = models.RefreshToken
    _token_id = RefreshTokenId
    _token = RefreshToken

    def _from_db(
        self,
        record: models.RefreshToken,
        user_role: UserRole,
    ) -> Tuple[RefreshTokenId, RefreshTokenClaims]:
        token_id = RefreshTokenId(record.id)
        return token_id, RefreshTokenClaims(
            token_id=token_id,
            subject=UserId(record.user_id),
            issued_at=record.created_at,
            expiration_time=record.expires_at,
            attributes=RefreshTokenAttributes(
                user_role=user_role,
            ),
        )

    def _to_db(self, claims: RefreshTokenClaims) -> models.RefreshToken:
        assert claims.expiration_time
        assert claims.subject
        user_id = int(claims.subject)
        return models.RefreshToken(
            user_id=user_id,
            created_at=claims.issued_at,
            expires_at=claims.expiration_time,
        )


class ApiKeyStore(
    _Store[
        ApiKeyClaims,
        ApiKey,
        ApiKeyId,
        models.ApiKey,
    ]
):
    _table = models.ApiKey
    _token_id = ApiKeyId
    _token = ApiKey

    def _from_db(
        self,
        record: models.ApiKey,
        user_role: UserRole,
    ) -> Tuple[ApiKeyId, ApiKeyClaims]:
        token_id = ApiKeyId(record.id)
        return token_id, ApiKeyClaims(
            token_id=token_id,
            subject=UserId(record.user_id),
            issued_at=record.created_at,
            expiration_time=record.expires_at,
            attributes=ApiKeyAttributes(
                user_role=user_role,
                name=record.name,
                description=record.description,
            ),
        )

    def _to_db(self, claims: ApiKeyClaims) -> models.ApiKey:
        assert claims.attributes
        assert claims.attributes.name
        assert claims.subject
        user_id = int(claims.subject)
        return models.ApiKey(
            user_id=user_id,
            name=claims.attributes.name,
            description=claims.attributes.description or None,
            created_at=claims.issued_at,
            expires_at=claims.expiration_time or None,
        )
