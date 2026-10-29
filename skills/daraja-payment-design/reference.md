# Ledger schema

PostgreSQL. It ports to MySQL or SQLite by swapping `BIGSERIAL`, `TIMESTAMPTZ` and `JSONB`. Amounts are integer shillings throughout.

```sql
-- One row per payment attempt: a collection (STK, C2B) or a payout (B2C, B2B, refund).
CREATE TABLE payments (
    id                          BIGSERIAL PRIMARY KEY,
    order_id                    TEXT NOT NULL,                 -- your order; also the STK AccountReference
    direction                   TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    kind                        TEXT NOT NULL,                 -- stk, c2b, b2c, b2b, reversal, refund
    amount                      BIGINT NOT NULL CHECK (amount > 0),
    phone                       TEXT,                          -- 2547XXXXXXXX
    state                       TEXT NOT NULL DEFAULT 'initiated'
        CHECK (state IN ('initiated', 'accepted', 'confirmed', 'failed', 'timed_out', 'reversed')),
    idempotency_key             TEXT NOT NULL UNIQUE,          -- never reused for a new attempt
    checkout_request_id         TEXT UNIQUE,                   -- STK
    originator_conversation_id  TEXT UNIQUE,                   -- B2C / B2B / reversal
    mpesa_receipt               TEXT UNIQUE,                   -- set on confirmation; duplicates fail here
    result_code                 TEXT,
    refund_of                   BIGINT REFERENCES payments(id), -- refunds and reversals point at the original
    short_payment               BOOLEAN NOT NULL DEFAULT FALSE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX payments_open ON payments (state, created_at) WHERE state IN ('accepted', 'timed_out');

-- Everything Daraja said, raw and append-only. Replay from here when parsing has a bug.
CREATE TABLE payment_events (
    id           BIGSERIAL PRIMARY KEY,
    payment_id   BIGINT REFERENCES payments(id),   -- NULL until matched (e.g. an orphan C2B payment)
    source       TEXT NOT NULL,                     -- request, response, callback, query, reconciliation
    payload      JSONB NOT NULL,
    received_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Double entry: every confirmed movement writes two rows that sum to zero.
CREATE TABLE ledger_entries (
    id          BIGSERIAL PRIMARY KEY,
    payment_id  BIGINT NOT NULL REFERENCES payments(id),
    account     TEXT NOT NULL,                      -- e.g. mpesa_float, customer:<id>, revenue, refunds
    amount      BIGINT NOT NULL,                    -- positive = debit, negative = credit
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (payment_id, account)                    -- a payment cannot post to the same account twice
);
```

## Example postings

A confirmed STK payment of KES 1,500 for order 1042:

| account | amount |
|---|---|
| `mpesa_float` | 1500 |
| `revenue` | -1500 |

A confirmed B2C refund of KES 500 of that payment (a new `payments` row with `refund_of` = the original):

| account | amount |
|---|---|
| `refunds` | 500 |
| `mpesa_float` | -500 |

## Confirming a payment safely

Do it in one transaction, so a duplicate callback changes nothing:

```sql
UPDATE payments
   SET state = 'confirmed', mpesa_receipt = $1, result_code = '0', updated_at = now()
 WHERE checkout_request_id = $2
   AND state IN ('accepted', 'timed_out')
   AND amount = $3
RETURNING id;
-- No row returned: already final, unknown ID, or wrong amount. Look it up and decide; never insert blindly.
```

Then insert the two `ledger_entries` rows for the returned `id`, in the same transaction.
