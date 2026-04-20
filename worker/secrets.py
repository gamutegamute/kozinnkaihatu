from __future__ import annotations

import os
from typing import Protocol


class SecretResolver(Protocol):
    def resolve(self, secret_ref: str) -> str | None: ...


class EnvSecretResolver:
    def resolve(self, secret_ref: str) -> str | None:
        value = os.getenv(secret_ref)
        if value is None:
            return None
        return value.strip() or None


def get_secret_resolver() -> SecretResolver:
    return EnvSecretResolver()
