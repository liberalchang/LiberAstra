"""core.security 单元测试。"""

from liberastra.core.security import (
    create_access_token,
    decode_access_token,
    generate_api_token,
    get_fernet,
    hash_api_token,
    hash_password,
    verify_password,
)


def test_password_roundtrip() -> None:
    hashed = hash_password("s3cret-password")
    assert verify_password("s3cret-password", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip() -> None:
    token = create_access_token("admin")
    assert decode_access_token(token) == "admin"
    assert decode_access_token(token + "tampered") is None


def test_api_token_generation() -> None:
    plaintext, token_hash, prefix = generate_api_token()
    assert plaintext.startswith("astra_")
    assert hash_api_token(plaintext) == token_hash
    assert plaintext.startswith(prefix[:8])


def test_fernet_roundtrip() -> None:
    fernet = get_fernet()
    secret = "sk-provider-key-123"
    assert fernet.decrypt(fernet.encrypt(secret.encode())).decode() == secret
