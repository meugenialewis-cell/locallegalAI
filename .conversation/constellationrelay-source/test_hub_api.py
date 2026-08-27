"""Test script for Memory Hub API"""
import requests
from v2.auth import create_agent_token

HUB_URL = "http://localhost:8000"

token = create_agent_token('pascal', 'test', long_lived=True)
print(f"Token generated: {token[:50]}...")

headers = {"Authorization": f"Bearer {token}"}

print("\n1. Testing root endpoint...")
try:
    resp = requests.get(f"{HUB_URL}/", timeout=5)
    print(f"   Status: {resp.status_code}")
    print(f"   Response: {resp.json()}")
except Exception as e:
    print(f"   Error: {e}")

print("\n2. Testing retrieve endpoint...")
try:
    resp = requests.get(
        f"{HUB_URL}/engrams/retrieve",
        headers=headers,
        params={"limit": 3},
        timeout=5
    )
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   Found {data.get('count', 0)} memories")
    else:
        print(f"   Response: {resp.text[:200]}")
except Exception as e:
    print(f"   Error: {e}")

print("\n3. Testing upload endpoint...")
try:
    resp = requests.post(
        f"{HUB_URL}/engrams/upload",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "digest": "Test memory from API test script",
            "importance": 3,
            "type": "semantic",
            "project": "hub_test"
        },
        timeout=5
    )
    print(f"   Status: {resp.status_code}")
    print(f"   Response: {resp.json() if resp.status_code == 200 else resp.text[:200]}")
except Exception as e:
    print(f"   Error: {e}")

print("\nDone!")
