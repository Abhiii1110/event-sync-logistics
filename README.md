# event-sync-logistics
README: 
Features so far: JWT auth with roles, vendor onboarding, overlap-safe booking with row locking, a concurrency test, idempotent PayPal capture with server-side amount verification.
Setup steps: clone, create a venv, pip install -r requirements.txt, copy .env.example to .env, create the MySQL database, run py manage.py migrate, then py manage.py runserver.
Notes: PayPal runs in sandbox only (PayPal doesn't support domestic payments in India), and the sandbox amount is a demo conversion.
Roadmap: vendor confirmation, webhooks, held payouts, React frontend, RAG and LangChain agents.

If you paste your current README, I can tighten it.

What to build next
Vendor confirmation and booking lifecycle: the vendor accepts or declines a paid booking, the booking is marked completed after the event, and cancellations follow clear rules. This finishes the state machine (PAID → VENDOR_CONFIRMED → COMPLETED).
Webhooks with idempotency: PayPal's PAYMENT.CAPTURE.COMPLETED handled safely if the user closes the browser mid-payment.
Held payouts: after the event plus N hours, release the vendor's share from your own ledger (Payout table).
React frontend: vendor marketplace, calendar grid, booking board and checkout.
