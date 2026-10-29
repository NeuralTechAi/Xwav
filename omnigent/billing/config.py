"""Operator-owned plans and model registry, independent of SDK release cycles."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, model_validator


class Model(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    upstream: str = Field(min_length=1, max_length=200)
    label: str = Field(default="", max_length=200)
    protocol: str = "chat/completions"
    output_token_field: (
        Literal["max_tokens", "max_completion_tokens", "max_output_tokens"] | None
    ) = None
    input_usd_per_million: float = Field(default=0, ge=0, allow_inf_nan=False)
    output_usd_per_million: float = Field(default=0, ge=0, allow_inf_nan=False)
    free: bool = False
    max_output_tokens: int = Field(default=4096, ge=1, le=131072)
    auto_candidates: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_protocol(self) -> Model:
        if self.protocol not in {"chat/completions", "responses", "messages"}:
            raise ValueError("Unsupported model wire protocol")
        return self


class Provider(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,47}$")
    label: str
    base_url: str
    api_key_env: str = ""
    omit_parallel_tool_calls: bool = False
    models: list[Model] = Field(default_factory=list)
    compatible_protocols: list[Literal["chat/completions", "responses", "messages"]] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_endpoint(self) -> Provider:
        url = urlsplit(self.base_url)
        if (
            url.scheme not in {"https", "http"}
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("Provider URL must be an operator-owned HTTP(S) endpoint")
        if len({m.id for m in self.models}) != len(self.models):
            raise ValueError("Duplicate model IDs")
        models = {m.id: m for m in self.models}
        for model in self.models:
            if len(set(model.auto_candidates)) != len(model.auto_candidates):
                raise ValueError("Duplicate Auto candidates")
            for candidate in model.auto_candidates:
                if candidate not in models or candidate == model.id:
                    raise ValueError("Auto candidates must reference other registered models")
                if models[candidate].auto_candidates or (
                    model.free and not models[candidate].free
                ):
                    raise ValueError(
                        "Auto candidates must be concrete models in the same usage tier"
                    )
        return self


class Plan(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    label: str
    monthly_usd: int = Field(ge=0)
    included_micro_usd: int = Field(ge=0)
    request_limit: int = Field(default=10000, ge=1, le=10000000)
    stripe_price_env: str = ""
    annual_monthly_usd: int | None = Field(default=None, ge=1)
    annual_stripe_price_env: str = ""
    token_limit: int = Field(default=0, ge=0)
    rollover: bool = False
    per_seat: bool = False
    included_credits: int | None = Field(default=None, ge=0)


class BillingConfig(BaseModel):
    public_url: str = "http://localhost:6767"
    database: str = ""
    plans: list[Plan]
    providers: list[Provider]
    byok_request_limit: int = Field(default=1000000, ge=1)
    max_inflight: int = Field(default=4, ge=1, le=128)
    queue_limit: int = Field(default=32, ge=1, le=1024)
    free_failover: bool = True
    free_failover_max_attempts: int = Field(default=8, ge=1, le=32)
    free_attempt_timeout_seconds: float = Field(default=45, ge=1, le=180)
    free_failover_timeout_seconds: float = Field(default=120, ge=1, le=600)
    free_failover_cooldown_seconds: int = Field(default=60, ge=1, le=3600)

    @model_validator(mode="after")
    def valid_registry(self) -> BillingConfig:
        for rows in (self.plans, self.providers):
            if len({p.id for p in rows}) != len(rows):
                raise ValueError("Duplicate registry IDs")
        free = next((p for p in self.plans if p.id == "free"), None)
        if free is None or free.monthly_usd:
            raise ValueError("A zero-price free plan is required")
        public = urlsplit(self.public_url)
        if (
            public.scheme not in {"https", "http"}
            or not public.hostname
            or public.username
            or public.password
            or public.query
            or public.fragment
        ):
            raise ValueError("public_url must be an HTTP(S) deployment URL without credentials")
        if public.scheme == "http" and public.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Remote billing deployments require HTTPS")
        if not self.database:
            raise ValueError("Configure a persistent billing database path")
        return self

    @classmethod
    def from_env(cls) -> BillingConfig | None:
        filename = os.environ.get("XWAV_BILLING_CONFIG")
        return cls.model_validate(json.loads(Path(filename).read_text())) if filename else None
