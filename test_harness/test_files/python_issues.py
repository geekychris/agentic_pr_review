"""Intentionally buggy Python code for testing the code review agent."""

import os
import sys
import json
import pickle  # noqa: unused, security concern

# SQL injection vulnerability
def get_user(db, username):
    query = f"SELECT * FROM users WHERE name = '{username}'"
    return db.execute(query)

# Missing error handling
def read_config(path):
    with open(path) as f:
        return json.load(f)

# Hardcoded credentials
API_KEY = "sk-abc123secretkey456"
DB_PASSWORD = "admin123"

# Off-by-one error
def get_items(items, count):
    result = []
    for i in range(count + 1):  # Bug: should be range(count)
        result.append(items[i])
    return result

# Race condition potential
counter = 0
def increment():
    global counter
    temp = counter
    temp += 1
    counter = temp

# Unsafe deserialization
def load_data(raw_bytes):
    return pickle.loads(raw_bytes)

# N+1 query pattern
def get_all_orders(db, users):
    orders = []
    for user in users:
        user_orders = db.execute(f"SELECT * FROM orders WHERE user_id = {user.id}")
        orders.extend(user_orders)
    return orders

# Command injection
def run_command(user_input):
    os.system(f"echo {user_input}")

# Missing null check
def process_response(response):
    data = response.json()
    return data["result"]["items"][0]["name"]
