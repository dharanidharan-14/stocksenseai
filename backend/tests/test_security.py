"""
StockSense AI - Security & Authentication Unit Tests
"""

import pytest
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token


def test_password_hashing():
    password = "SuperSecurePassword123"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_password_truncation_safe():
    long_pass = "A" * 100
    hashed = hash_password(long_pass)
    assert verify_password(long_pass, hashed) is True
    assert verify_password(long_pass[:72], hashed) is True


def test_jwt_token_flow():
    payload = {"sub": "user-uuid-123", "username": "shopkeeper", "role": "admin"}
    token = create_access_token(payload)

    decoded = decode_access_token(token)
    assert decoded["sub"] == "user-uuid-123"
    assert decoded["username"] == "shopkeeper"
    assert "exp" in decoded
