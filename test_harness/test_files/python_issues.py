"""Intentionally buggy Python code for testing the code review agent."""

import os
import sys  # noqa: F401 — unused import (suggestion-level)
import json
import pickle  # noqa: unused, security concern
import time  # noqa: F401 — unused import


# ── ERROR-level: SQL injection vulnerability ──
def get_user(db, username):
    query = f"SELECT * FROM users WHERE name = '{username}'"
    return db.execute(query)


# ── ERROR-level: Hardcoded credentials ──
API_KEY = "sk-abc123secretkey456"
DB_PASSWORD = "admin123"


# ── ERROR-level: Command injection ──
def run_command(user_input):
    os.system(f"echo {user_input}")


# ── ERROR-level: Unsafe deserialization ──
def load_data(raw_bytes):
    return pickle.loads(raw_bytes)


# ── WARNING-level: Broad exception clause ──
def read_config(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


# ── WARNING-level: Magic numbers ──
def calculate_price(quantity):
    base = quantity * 19.99
    tax = base * 0.0825
    shipping = 5.99 if quantity < 3 else 0
    discount = base * 0.15 if quantity > 10 else 0
    return base + tax + shipping - discount


# ── WARNING-level: Mutable default argument ──
def add_item(item, items=[]):
    items.append(item)
    return items


# ── WARNING-level: print() instead of logging ──
def process_batch(records):
    print(f"Processing {len(records)} records")
    results = []
    for r in records:
        print(f"  handling record {r['id']}")
        results.append(r)
    print("Done")
    return results


# ── SUGGESTION-level: Missing type hints on public function ──
def get_items(items, count):
    result = []
    for i in range(count + 1):  # Bug: off-by-one
        result.append(items[i])
    return result


# ── SUGGESTION-level: Inefficient string concatenation in loop ──
def build_report(entries):
    report = ""
    for entry in entries:
        report = report + f"- {entry['name']}: {entry['value']}\n"
    return report


# ── SUGGESTION-level: Could use dict comprehension ──
def index_by_id(items):
    result = {}
    for item in items:
        result[item["id"]] = item
    return result


# ── ERROR-level: Threading deadlock — locks acquired in opposite order ──
import threading

lock_accounts = threading.Lock()
lock_ledger = threading.Lock()

def transfer_funds(from_acct, to_acct, amount):
    with lock_accounts:
        with lock_ledger:  # Acquires accounts then ledger
            from_acct["balance"] -= amount
            to_acct["balance"] += amount

def reconcile_ledger(accounts, ledger):
    with lock_ledger:
        with lock_accounts:  # Acquires ledger then accounts — DEADLOCK!
            for acct in accounts:
                ledger[acct["id"]] = acct["balance"]


# ── ERROR-level: Generator exhaustion — reusing consumed iterator ──
def process_pipeline(records):
    filtered = (r for r in records if r["active"])
    count = sum(1 for _ in filtered)    # Exhausts the generator
    results = list(filtered)            # BUG: always empty, generator spent
    return {"count": count, "results": results}


# ── WARNING-level: Late binding closure in loop ──
def make_multipliers():
    return [lambda x: x * i for i in range(5)]
    # BUG: all lambdas capture `i` by reference, all will multiply by 4


# ── INFO-level: TODO / FIXME comments ──
def process_response(response):
    # TODO: add retry logic for transient failures
    # FIXME: this will crash if response has no 'result' key
    data = response.json()
    return data["result"]["items"][0]["name"]


# ── WARNING-level: N+1 query pattern ──
def get_all_orders(db, users):
    orders = []
    for user in users:
        user_orders = db.execute(
            f"SELECT * FROM orders WHERE user_id = {user.id}"
        )
        orders.extend(user_orders)
    return orders


# ── SUGGESTION-level: Function does too many things ──
def handle_upload(request):
    file = request.files["upload"]
    if not file.filename.endswith(".csv"):
        return {"error": "only CSV allowed"}
    content = file.read().decode("utf-8")
    lines = content.strip().split("\n")
    headers = lines[0].split(",")
    rows = []
    for line in lines[1:]:
        values = line.split(",")
        row = dict(zip(headers, values))
        rows.append(row)
    # validate
    for row in rows:
        if not row.get("email"):
            return {"error": "missing email"}
    # save
    saved = 0
    for row in rows:
        save_to_db(row)
        saved += 1
    return {"saved": saved}


def save_to_db(row):
    pass  # stub
