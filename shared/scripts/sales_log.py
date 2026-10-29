#!/usr/bin/env python3
"""A CSV sales log for an agent that sells on its own, without an app or database.

Usage:
  python scripts/sales_log.py add <order_id> <phone> <amount> "<items>"   # before the STK Push
  python scripts/sales_log.py set <order_id> <status> [receipt]          # after mpesa_get_result
  python scripts/sales_log.py show [order_id]
  python scripts/sales_log.py open                                       # orders not yet final
Status: pending, paid, failed, cancelled, refunded, unknown. The file is ./sales.csv, or
$MPESA_SALES_LOG. Amounts are whole shillings.
"""
import csv
import os
import sys
from datetime import datetime, timedelta, timezone

FIELDS = ["order_id", "created_eat", "phone", "amount", "items", "status", "receipt", "updated_eat"]
STATUSES = {"pending", "paid", "failed", "cancelled", "refunded", "unknown"}
FINAL = {"paid", "failed", "cancelled", "refunded"}
EAT = timezone(timedelta(hours=3))


def path():
    return os.environ.get("MPESA_SALES_LOG") or "sales.csv"


def now():
    return datetime.now(EAT).strftime("%Y-%m-%d %H:%M:%S")


def load():
    if not os.path.exists(path()):
        return []
    with open(path(), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def save(rows):
    tmp = path() + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path())


def show(rows):
    for r in rows:
        print(f"{r['order_id']:<16} {r['status']:<10} KES {r['amount']:>7}  {r['phone']}  "
              f"{r['receipt'] or '-':<12} {r['items']}")


def main(args):
    if not args:
        sys.exit(__doc__)
    rows = load()
    cmd = args[0]
    if cmd == "add" and len(args) == 5:
        order_id, phone, amount, items = args[1:]
        if any(r["order_id"] == order_id for r in rows):
            sys.exit(f"order {order_id} already exists: use a new order ID for a new attempt")
        if not amount.isdigit() or int(amount) < 1:
            sys.exit("amount must be whole shillings")
        rows.append({"order_id": order_id, "created_eat": now(), "phone": phone, "amount": amount,
                     "items": items, "status": "pending", "receipt": "", "updated_eat": now()})
        save(rows)
        print(f"added {order_id} (pending)")
    elif cmd == "set" and len(args) in (3, 4):
        order_id, status = args[1], args[2]
        if status not in STATUSES:
            sys.exit(f"status must be one of {', '.join(sorted(STATUSES))}")
        row = next((r for r in rows if r["order_id"] == order_id), None)
        if row is None:
            sys.exit(f"no order {order_id}")
        refund = row["status"] == "paid" and status == "refunded"
        if row["status"] in FINAL and status != row["status"] and not refund:
            sys.exit(f"order {order_id} is already {row['status']}; record a new order instead")
        if status == "paid" and len(args) < 4:
            sys.exit("paid needs the M-Pesa receipt from the confirmed result")
        row["status"], row["updated_eat"] = status, now()
        if len(args) == 4:
            row["receipt"] = args[3]
        save(rows)
        print(f"{order_id} -> {status}")
    elif cmd == "show":
        show([r for r in rows if len(args) < 2 or r["order_id"] == args[1]])
    elif cmd == "open":
        show([r for r in rows if r["status"] not in FINAL])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
