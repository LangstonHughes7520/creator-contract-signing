from __future__ import annotations

import os
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from signing_client import InfraiError, InfraiPdfSigner


class ContractIngestion(BaseModel):
    contract_id: str = Field(min_length=1)
    creator_id: str = Field(min_length=1)
    pdf: str = Field(min_length=1)
    cert_pem: str = Field(min_length=1)
    key_pem: str = Field(min_length=1)
    signing_location: str = Field(min_length=1)
    retention_days: int = Field(default=30, ge=1, le=365)


class ProcessingJob(BaseModel):
    contract_id: str
    creator_id: str
    job_id: str
    state: Literal["processing", "signed", "rejected"]


class CreatorDelivery(BaseModel):
    contract_id: str
    creator_id: str
    signed_pdf: str


app = FastAPI(title="Media contract signing service")
jobs: dict[str, ProcessingJob] = {}
deliveries: dict[str, CreatorDelivery] = {}


def signer_from_environment() -> InfraiPdfSigner:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set INFRAI_API_KEY before starting the service")
    return InfraiPdfSigner(api_key)


@app.post("/contracts", response_model=ProcessingJob, status_code=202)
def ingest_contract(request: ContractIngestion) -> ProcessingJob:
    signer = signer_from_environment()
    try:
        result = signer.sign(
            pdf=request.pdf,
            cert_pem=request.cert_pem,
            key_pem=request.key_pem,
            reason=f"Media streaming agreement for {request.creator_id}",
            location=request.signing_location,
            retention_days=request.retention_days,
            idempotency_key=f"contract:{request.contract_id}",
        )
    except InfraiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.details) from exc

    job = ProcessingJob(
        contract_id=request.contract_id,
        creator_id=request.creator_id,
        job_id=result.job_id,
        state="processing",
    )
    jobs[result.job_id] = job
    return job


@app.post("/jobs/{job_id}/refresh", response_model=ProcessingJob)
def refresh_job(job_id: str) -> ProcessingJob:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Processing job not found")
    try:
        result = signer_from_environment().get_job(job_id)
    except InfraiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.details) from exc

    status = str(result.get("status", "processing"))
    if status == "completed":
        signed_pdf = str(result["output"])
        job = job.model_copy(update={"state": "signed"})
        jobs[job_id] = job
        deliveries[job.contract_id] = CreatorDelivery(
            contract_id=job.contract_id,
            creator_id=job.creator_id,
            signed_pdf=signed_pdf,
        )
    elif status == "failed":
        job = job.model_copy(update={"state": "rejected"})
        jobs[job_id] = job
    return job


@app.get("/contracts/{contract_id}/delivery", response_model=CreatorDelivery)
def creator_delivery(contract_id: str) -> CreatorDelivery:
    delivery = deliveries.get(contract_id)
    if not delivery:
        raise HTTPException(status_code=409, detail="Signed contract is not ready for delivery")
    return delivery
