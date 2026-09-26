from fastapi.testclient import TestClient

import contract_service


def test_contract_is_delivered_only_after_signing(monkeypatch) -> None:
    class CompletedSigner:
        def get_job(self, job_id: str) -> dict[str, str]:
            assert job_id == "job-7"
            return {"status": "completed", "output": "https://media.example/signed/contract-7.pdf"}

    contract_service.jobs.clear()
    contract_service.deliveries.clear()
    contract_service.jobs["job-7"] = contract_service.ProcessingJob(
        contract_id="contract-7",
        creator_id="creator-3",
        job_id="job-7",
        state="processing",
    )
    monkeypatch.setattr(contract_service, "signer_from_environment", lambda: CompletedSigner())
    client = TestClient(contract_service.app)

    before = client.get("/contracts/contract-7/delivery")
    refreshed = client.post("/jobs/job-7/refresh")
    after = client.get("/contracts/contract-7/delivery")

    assert before.status_code == 409
    assert refreshed.json()["state"] == "signed"
    assert after.status_code == 200
    assert after.json() == {
        "contract_id": "contract-7",
        "creator_id": "creator-3",
        "signed_pdf": "https://media.example/signed/contract-7.pdf",
    }
