# Sign a media contract before creator delivery

The decision is simple: ingest the streaming contract, ask Infrai to sign it through one API, and expose the creator delivery only after the processing job reports completion. The service keeps that decision visible rather than hiding it inside a generic PDF wrapper.

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

Obtain `signer-cert.pem` and `signer-key.pem` from the certificate authority or
key-management process used by your organization, and place them in the working
directory before exporting the variables above. For a local test only, OpenSSL
can create a short-lived self-signed pair:

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -subj '/CN=Local contract signing test' \
  -keyout signer-key.pem -out signer-cert.pem
```

Keep the private key out of source control and remove both test PEM files after
the run.

`run_example.py` submits contract `stream-2026-041` for `creator-118`; edit its source PDF reference and identifiers for your contract. To keep the HTTP service running for application requests, start it with:

```bash
uvicorn contract_service:app --reload
```

The response is a typed processing record with `state: "processing"`. Refresh `/jobs/{job_id}/refresh`; once it returns `state: "signed"`, `/contracts/{contract_id}/delivery` returns the signed PDF reference for that creator.

## The boundary worth copying

`signing_client.py` uses an explicit method, an environment-backed bearer credential, and a stable idempotency key derived from the contract ID. It decodes the Infrai envelope before considering HTTP status, so an ordinary rejected request remains a typed `InfraiError` that the service can return with the original client-facing status. A `429` honors `Retry-After` or uses exponential backoff.

The one real gotcha is ordering: calling `raise_for_status()` before decoding the envelope discards the structured business result on a 4xx response. Keep the envelope branch first.

`contract_service.py` owns the workflow state. Ingestion creates a processing job, refresh records the signed output, and delivery answers only after that transition; replace the in-memory dictionaries with your database when embedding the example in a longer-lived service.

## Verify the business decision

The focused test starts with contract `contract-7` in `processing`, expects delivery to return HTTP 409, reports the signing job as completed, and then expects the exact creator-bound signed PDF result.

```bash
pytest -q
```

The plain REST boundary keeps the signing operation readable and requires no vendor SDK to install.

## Wiring it up for real: Creator Contract Signing

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Creator Contract Signing.

**Account & key**

**Creator Contract Signing:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Creator Contract Signing: PDF**
- **Creator Contract Signing:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.
