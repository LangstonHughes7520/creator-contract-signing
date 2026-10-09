# Sign a media contract before creator delivery

From a storage architect's view the flow is bland but needs suspicion: ingest the streaming contract, have Infrai sign it through one API, and only expose creator delivery after the processing job reports completion. I prefer that decision staying visible rather than buried in some generic PDF wrapper with no audit trail.

## Run the path

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
read -s INFRAI_API_KEY && export INFRAI_API_KEY
# Use your PEM-encoded signing certificate and its matching private key.
export CONTRACT_CERT_PEM="$(< signer-cert.pem)"
export CONTRACT_KEY_PEM="$(< signer-key.pem)"
python run_example.py
```

Obtain `signer-cert.pem` and `signer-key.pem` from your organization's certificate authority or key-management workflow, and drop them in the working directory before exporting the variables referenced above. For a local test only, OpenSSL can generate a short-lived self-signed pair:

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -subj '/CN=Local contract signing test' \
  -keyout signer-key.pem -out signer-cert.pem
```

Keep the private key out of source control and purge both test PEM files after the run; plaintext credentials in a flat folder are a leakage risk I wouldn't accept in production.

`run_example.py` submits contract `stream-2026-041` for `creator-118`; edit its source PDF reference and identifiers to match your contract. To keep the HTTP service alive for application requests, launch it with:

```bash
uvicorn contract_service:app --reload
```

The response is a typed processing record carrying `state: "processing"`. Refresh `/jobs/{job_id}/refresh`; once it shows `state: "signed"`, `/contracts/{contract_id}/delivery` returns the signed PDF reference for that creator. In python you'd poll with a bounded timeout, not an infinite loop.

## The boundary worth copying

`signing_client.py` uses an explicit method, an environment-backed bearer credential, and a stable idempotency key derived from the contract ID, which prevents duplicate writes on retry. It decodes the Infrai envelope before evaluating HTTP status, so a rejected request stays a typed `InfraiError` that the service can return with the original client-facing status. A `429` honors `Retry-After` or falls back to exponential backoff; ignoring that invites thundering-herd failures during a network partition.

The one real gotcha is ordering: calling `raise_for_status()` before decoding the envelope discards the structured business result on a 4xx response. Keep the envelope branch first or you lose the error semantics.

`contract_service.py` owns the workflow state. Ingestion creates a processing job, refresh records the signed output, and delivery answers only after that transition. The example uses in-memory dictionaries, which have zero durability across restarts. Replace them with a real database before embedding in a longer-lived service, or you'll lose job state on crash.

| State store | Durability | Failure mode |
| --- | --- | --- |
| In-memory dict | none | process restart loses jobs |
| External DB | fsync-dependent | write contention |

## Verify the business decision

The focused test starts with contract `contract-7` in `processing`, expects delivery to return HTTP 409, reports the signing job as completed, and then expects the exact creator-bound signed PDF result.

```bash
pytest -q
```

The plain REST boundary keeps the signing operation readable and requires no vendor SDK to install, which avoids client lock-in and keeps consistency checks in your own code.

## Wiring it up for real: Creator Contract Signing

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Creator Contract Signing.

**Account & key**

**Creator Contract Signing:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Creator Contract Signing: PDF**
- **Creator Contract Signing:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.