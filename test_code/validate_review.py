"""Test file to validate the GitHub Actions auto-review workflow."""

import os
import sqlite3


# SQL injection — should be flagged as error
def get_user(db_path, username):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE name = '" + username + "'")
    return cursor.fetchone()


# Hardcoded secret — should be flagged as error
API_KEY = "sk-proj-abc123-very-secret-key-do-not-commit"


# Command injection — should be flagged as error
def ping_host(hostname):
    os.system(f"ping -c 1 {hostname}")


# Mutable default argument — should be flagged as warning
def add_item(item, items=[]):
    items.append(item)
    return items


# Broad exception swallowing — should be flagged as warning
def parse_config(data):
    try:
        return int(data)
    except Exception:
        pass


# String concatenation in loop — should be flagged as suggestion
def build_csv(rows):
    output = ""
    for row in rows:
        output += ",".join(str(x) for x in row) + "\n"
    return output


# TODO: add proper logging — should be flagged as info
def process(x):
    print(f"Processing {x}")
    return x * 2
