# event-sync-logistics
README: 
Features so far: JWT auth with roles, vendor onboarding, overlap-safe booking with row locking, a concurrency test, idempotent PayPal capture with server-side amount verification.
Setup steps: clone, create a venv, pip install -r requirements.txt, copy .env.example to .env, create the MySQL database, run py manage.py migrate, then py manage.py runserver.
Notes: PayPal runs in sandbox only (PayPal doesn't support domestic payments in India), and the sandbox amount is a demo conversion.
Roadmap: vendor confirmation, webhooks, held payouts, React frontend, RAG and LangChain agents.

Booking lifecycle: PENDING_PAYMENT → PAID → VENDOR_CONFIRMED → COMPLETED, with cancel and refund branches.
Cancellation policy: 100% refund when the vendor cancels or declines. When the client cancels a confirmed booking: 100% at 7+ days before, 50% at 2 to 7 days, none under 2 days.
Design notes: a single transition table, row locking on every state change, refunds issued after commit and retried by a background job, and idempotent refund requests.


