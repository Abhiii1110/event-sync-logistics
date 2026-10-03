# event-sync-logistics
README: 
Features so far: JWT auth with roles, vendor onboarding, overlap-safe booking with row locking, a concurrency test, idempotent PayPal capture with server-side amount verification.
Setup steps: clone, create a venv, pip install -r requirements.txt, copy .env.example to .env, create the MySQL database, run py manage.py migrate, then py manage.py runserver.
Notes: PayPal runs in sandbox only (PayPal doesn't support domestic payments in India), and the sandbox amount is a demo conversion.
Roadmap: vendor confirmation, webhooks, held payouts, React frontend, RAG and LangChain agents.



