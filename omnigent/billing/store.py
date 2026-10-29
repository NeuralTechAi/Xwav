"""Single-node SQLite ledger with atomic reservations and encrypted BYOK credentials."""

from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path
from typing import Any, cast

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import CursorResult

from omnigent.db.utils import make_named_managed_session_maker


class BillingStore:
    def __init__(self, path: str, encryption_key: str):
        self.cipher = Fernet(encryption_key.encode())
        db = Path(path).expanduser().resolve()
        db.parent.mkdir(parents=True, exist_ok=True)
        db.touch(mode=0o600, exist_ok=True)
        db.chmod(0o600)
        self.engine = create_engine(f"sqlite:///{db}", connect_args={"timeout": 30})
        self.session = make_named_managed_session_maker(
            self.engine, query_name_prefix="xwav.billing", immediate=True
        )
        with self.session("initialize") as session:
            session.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS billing_accounts (owner TEXT PRIMARY "
                    "KEY, data TEXT NOT NULL)"
                )
            )
            session.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS billing_usage (owner TEXT, period "
                    "TEXT, mode TEXT, spent INTEGER NOT NULL DEFAULT 0, requests "
                    "INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(owner, period, mode))"
                )
            )
            session.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS billing_keys (owner TEXT, provider "
                    "TEXT, secret TEXT NOT NULL, PRIMARY KEY(owner, provider))"
                )
            )
            session.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS billing_tokens (hash TEXT PRIMARY KEY,"
                    " owner TEXT UNIQUE NOT NULL)"
                )
            )
            session.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS billing_members (team TEXT NOT NULL, "
                    "member TEXT PRIMARY KEY, accepted INTEGER NOT NULL DEFAULT 0)"
                )
            )
            session.execute(
                text("CREATE TABLE IF NOT EXISTS billing_events (id TEXT PRIMARY KEY)")
            )
        with self.session("upgrade_token_ledger") as session:
            columns = session.execute(text("PRAGMA table_info(billing_usage)")).all()
            if not any(row[1] == "tokens" for row in columns):
                session.execute(
                    text("ALTER TABLE billing_usage ADD COLUMN tokens INTEGER NOT NULL DEFAULT 0")
                )

    def account(self, owner: str) -> dict[str, Any]:
        with self.session("read_account") as session:
            raw = session.execute(
                text("SELECT data FROM billing_accounts WHERE owner=:o"), {"o": owner}
            ).scalar()
        return json.loads(raw) if raw else {"plan": "free", "mode": "free", "status": "free"}

    def update(self, owner: str, **fields: Any) -> dict[str, Any]:
        with self.session("update_account") as session:
            raw = session.execute(
                text("SELECT data FROM billing_accounts WHERE owner=:o"), {"o": owner}
            ).scalar()
            data = json.loads(raw) if raw else {"plan": "free", "mode": "free", "status": "free"}
            data.update(fields)
            session.execute(
                text(
                    "INSERT INTO billing_accounts(owner,data) VALUES (:o,:d) ON "
                    "CONFLICT(owner) DO UPDATE SET data=:d"
                ),
                {"o": owner, "d": json.dumps(data)},
            )
        return data

    def rotate_token(self, owner: str) -> str:
        token = "xwav_" + secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.session("rotate_gateway_token") as session:
            session.execute(text("DELETE FROM billing_tokens WHERE owner=:o"), {"o": owner})
            session.execute(
                text("INSERT INTO billing_tokens VALUES (:h,:o)"), {"h": digest, "o": owner}
            )
        self.update(owner, token_hash=digest)
        return token

    def revoke_token(self, owner: str) -> None:
        with self.session("revoke_gateway_token") as session:
            session.execute(text("DELETE FROM billing_tokens WHERE owner=:o"), {"o": owner})
        self.update(owner, token_hash="")

    def token_owner(self, token: str) -> str:
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.session("authenticate_gateway") as session:
            owner = session.execute(
                text("SELECT owner FROM billing_tokens WHERE hash=:h"), {"h": digest}
            ).scalar()
        if owner is None:
            raise HTTPException(401, "Invalid or revoked Xwav gateway token")
        return owner

    def members(self, team: str) -> list[dict[str, Any]]:
        with self.session("team_roster") as session:
            return [
                dict(row._mapping)
                for row in session.execute(
                    text(
                        "SELECT member,accepted FROM billing_members WHERE team=:t ORDER BY member"
                    ),
                    {"t": team},
                )
            ]

    def invite(self, team: str, member: str) -> None:
        if team == member:
            raise HTTPException(400, "The subscription owner already has a seat")
        with self.session("allocate_team_seat") as session:
            raw = session.execute(
                text("SELECT data FROM billing_accounts WHERE owner=:o"), {"o": team}
            ).scalar()
            account = json.loads(raw) if raw else {}
            count = session.execute(
                text("SELECT COUNT(*) FROM billing_members WHERE team=:t"), {"t": team}
            ).scalar()
            if (count or 0) + 1 >= account.get("seats", 1):
                raise HTTPException(409, "All purchased seats are allocated")
            existing = session.execute(
                text("SELECT team FROM billing_members WHERE member=:m"), {"m": member}
            ).scalar()
            if existing is not None:
                raise HTTPException(
                    409, "This account already has a team invitation or membership"
                )
            session.execute(
                text("INSERT INTO billing_members VALUES (:t,:m,0)"), {"t": team, "m": member}
            )

    def membership(self, member: str) -> dict[str, Any] | None:
        with self.session("read_membership") as session:
            row = session.execute(
                text("SELECT team,accepted FROM billing_members WHERE member=:m"), {"m": member}
            ).first()
        return dict(row._mapping) if row else None

    def accept(self, member: str) -> None:
        with self.session("accept_team_invitation") as session:
            session.execute(
                text("UPDATE billing_members SET accepted=1 WHERE member=:m"), {"m": member}
            )

    def remove_member(self, team: str, member: str) -> None:
        with self.session("release_team_seat") as session:
            session.execute(
                text("DELETE FROM billing_members WHERE team=:t AND member=:m"),
                {"t": team, "m": member},
            )

    def key(self, owner: str, provider: str, value: str | None = None) -> str | None:
        with self.session("provider_credential") as session:
            args = {"o": owner, "p": provider}
            if value is not None:
                if not value:
                    session.execute(
                        text("DELETE FROM billing_keys WHERE owner=:o AND provider=:p"), args
                    )
                else:
                    # Bind ciphertext to both owner and provider to detect swapped rows.
                    args["s"] = self.cipher.encrypt(
                        json.dumps([owner, provider, value]).encode()
                    ).decode()
                    session.execute(
                        text(
                            "INSERT INTO billing_keys VALUES (:o,:p,:s) ON "
                            "CONFLICT(owner,provider) DO UPDATE SET secret=:s"
                        ),
                        args,
                    )
                return None
            raw = session.execute(
                text("SELECT secret FROM billing_keys WHERE owner=:o AND provider=:p"), args
            ).scalar()
        if raw is None:
            return None
        saved_owner, saved_provider, key = json.loads(self.cipher.decrypt(raw.encode()))
        if (saved_owner, saved_provider) != (owner, provider):
            raise HTTPException(503, "Credential storage unavailable")
        return key

    def key_ids(self, owner: str) -> list[str]:
        with self.session("list_credentials") as session:
            return list(
                session.execute(
                    text("SELECT provider FROM billing_keys WHERE owner=:o"), {"o": owner}
                ).scalars()
            )

    def usage(self, owner: str, period: str, mode: str) -> dict[str, int]:
        with self.session("read_usage") as session:
            row = session.execute(
                text(
                    "SELECT spent,requests,tokens FROM billing_usage WHERE owner=:o "
                    "AND period=:p AND mode=:m"
                ),
                {"o": owner, "p": period, "m": mode},
            ).first()
        return {
            "spent_micro_usd": row[0] if row else 0,
            "requests": row[1] if row else 0,
            "tokens": row[2] if row else 0,
        }

    def reserve(
        self,
        owner: str,
        period: str,
        mode: str,
        amount: int,
        limit: int | None,
        requests: int,
        tokens: int = 0,
        token_limit: int = 0,
        *,
        count_request: bool = True,
    ) -> None:
        with self.session("reserve_inference") as session:
            args = {
                "o": owner,
                "p": period,
                "m": mode,
                "a": amount,
                "l": limit,
                "r": requests,
                "t": tokens,
                "tl": token_limit,
                "rc": int(count_request),
            }
            session.execute(
                text("INSERT OR IGNORE INTO billing_usage(owner,period,mode) VALUES (:o,:p,:m)"),
                args,
            )
            result = session.execute(
                text(
                    "UPDATE billing_usage SET "
                    "spent=spent+:a,requests=requests+:rc,tokens=tokens+:t WHERE "
                    "owner=:o AND period=:p AND mode=:m AND (:l IS NULL OR "
                    "spent+:a<=:l) AND requests+:rc<=:r AND (:tl=0 OR tokens+:t<=:tl)"
                ),
                args,
            )
            if cast(CursorResult, result).rowcount != 1:
                raise HTTPException(
                    429, "Usage limit reached. Choose BYOK, upgrade, or wait for reset."
                )

    def settle(
        self,
        owner: str,
        period: str,
        mode: str,
        reserved: int,
        actual: int,
        reserved_tokens: int = 0,
        actual_tokens: int = 0,
    ) -> None:
        with self.session("settle_inference") as session:
            session.execute(
                text(
                    "UPDATE billing_usage SET "
                    "spent=MAX(0,spent+:delta),tokens=MAX(0,tokens+:tdelta) WHERE "
                    "owner=:o AND period=:p AND mode=:m"
                ),
                {
                    "o": owner,
                    "p": period,
                    "m": mode,
                    "delta": actual - reserved,
                    "tdelta": actual_tokens - reserved_tokens,
                },
            )

    def event(self, event_id: str, owner: str, fields: dict[str, Any]) -> None:
        with self.session("apply_subscription_event") as session:
            if session.execute(
                text("SELECT id FROM billing_events WHERE id=:id"), {"id": event_id}
            ).first():
                return
            raw = session.execute(
                text("SELECT data FROM billing_accounts WHERE owner=:o"), {"o": owner}
            ).scalar()
            data = json.loads(raw) if raw else {"mode": "free"}
            if data.get("subscription_created", 0) > fields.get("subscription_created", 0):
                return
            data.update(fields)
            session.execute(
                text(
                    "INSERT INTO billing_accounts VALUES (:o,:d) ON CONFLICT(owner) DO"
                    " UPDATE SET data=:d"
                ),
                {"o": owner, "d": json.dumps(data)},
            )
            session.execute(text("INSERT INTO billing_events VALUES (:id)"), {"id": event_id})
