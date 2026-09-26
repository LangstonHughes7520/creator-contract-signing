import os

from fastapi.testclient import TestClient

from contract_service import app


if __name__ == "__main__":
    cert_pem = os.environ["CONTRACT_CERT_PEM"]
    key_pem = os.environ["CONTRACT_KEY_PEM"]
    client = TestClient(app)
    response = client.post(
        "/contracts",
        json={
            "contract_id": "stream-2026-041",
            "creator_id": "creator-118",
            "pdf": "https://media.example/contracts/stream-2026-041.pdf",
            "cert_pem": cert_pem,
            "key_pem": key_pem,
            "signing_location": "Shanghai",
            "retention_days": 30,
        },
    )
    print(response.status_code, response.json())
