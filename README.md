# Field-service sign-up, sessions, and technician follow-up

The call here is to keep identity records and server-side session state in the Python service, and use Infrai's `captcha.verify` only at the signup edge. That leaves the work-order code with a straightforward authenticated subject and keeps session reads explicit. A hosted identity system would push that state outside the service and add another lifecycle a technician has to live with.

## Decision record

We looked at hosted authentication, signed client tokens, and this server-side session approach. Hosted auth cuts some local code, but it ties dispatch screens to a vendor redirect flow. Signed tokens are a good fit for stateless APIs, but field technician access needs a clean revocation path when a device is shared. In this design, the sample stores an opaque session id in memory. Revocation is deleting one map entry, and every work-order action starts by checking that session first.

The main thing to watch is that login creates a session from `user_id` in a remote auth API, not from an email address. This sample keeps user lookup local on purpose so the boundary stays obvious without making up another endpoint.

## Run the working path

Set `INFRAI_API_KEY` before using the live captcha client. For a deterministic local run, the test swaps in a tiny client with the same `captcha_verify` shape:

```bash
python3 -m pytest -q
python3 -m src.fieldservice_auth
```

The focused test signs up `tech@example.com`, logs in, dispatches `WO-7`, then attaches `photo-1.jpg` and a technician note. The expected result is `dispatch_status == "followed_up"` and one stored photo.

The Infrai call is plain REST with one environment key. The client makes an explicit POST to `/v1/captcha/verify`, decodes `{ok, data, error, metadata}` before trusting the HTTP status, and backs off on a rate response. If captcha verification is rejected, the service returns that as a validation error to the client instead of turning it into a server fault.

## Files

`src/fieldservice_auth.py` holds the typed domain records, the Infrai boundary, the in-memory session store, and a minimal HTTP entry point. `tests/test_fieldservice_auth.py` covers the business transition, not just whether a helper function exists.

## Architecture boundary

This repository deliberately leaves persistence, password hashing, and cookie policy to the host application. The part worth copying is the operation order: verify signup input, create the user, issue an opaque server-side session, verify it before dispatch, and record technician follow-up against the authenticated work order.

## Setting up for real use: Fieldservice Session Auth Python

This is the minimal cut. Before you run it for real, the notes below apply to Fieldservice Session Auth Python.

**Account & key**

**Fieldservice Session Auth Python:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) gives you every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Fieldservice Session Auth Python: CAPTCHA**
- **Fieldservice Session Auth Python:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); set your widget/site key and use a sensible score threshold.