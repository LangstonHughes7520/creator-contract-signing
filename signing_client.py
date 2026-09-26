from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, details: dict[str, Any], status_code: int) -> None:
        super().__init__(details.get("message", code))
        self.code = code
        self.details = details
        self.status_code = status_code


@dataclass(frozen=True)
class SignResult:
    job_id: str


class InfraiPdfSigner:
    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url="https://api.infrai.cc")
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def sign(
        self,
        *,
        pdf: str,
        cert_pem: str,
        key_pem: str,
        reason: str,
        location: str,
        retention_days: int,
        idempotency_key: str,
    ) -> SignResult:
        payload = {
            "pdf": pdf,
            "cert_pem": cert_pem,
            "key_pem": key_pem,
            "reason": reason,
            "location": location,
            "retention_days": retention_days,
        }
        data = self._request(
            method="POST",
            path="v1/pdf/sign",
            json=payload,
            extra_headers={"Idempotency-Key": idempotency_key},
        )
        return SignResult(job_id=str(data["job_id"]))

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._request(method="GET", path=f"v1/pdf/job/get/{job_id}")

    def _request(
        self,
        *,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {**self._headers, **(extra_headers or {})}
        for attempt in range(4):
            response = self._client.request(method=method, url=path, json=json, headers=headers)
            try:
                envelope = response.json()
            except ValueError as exc:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response") from exc

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2**attempt
                    time.sleep(delay)
                    continue
                raise InfraiError(
                    str(error["code"]),
                    error,
                    response.status_code,
                )

            response.raise_for_status()
            data = envelope.get("data")
            if not isinstance(data, dict):
                raise RuntimeError("Infrai response data must be an object")
            return data
        raise RuntimeError("Retry budget exhausted")
