"""混合加密工具 — AES-256-GCM + RSA-OAEP

用法:
    from chaoxing_sign.utils.crypto import (
        generate_rsa_keypair, encrypt_hybrid, decrypt_hybrid,
        load_private_key, load_public_key,
    )

    # 生成密钥对
    private_pem, public_pem = generate_rsa_keypair()

    # 加密
    encrypted = encrypt_hybrid({"phone": "13800138000", "password": "secret"}, public_pem)

    # 解密
    data = decrypt_hybrid(encrypted, private_pem)  # -> {"phone": "...", "password": "..."}
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes

# RSA 密钥大小
RSA_KEY_SIZE = 2048

# AES-GCM 参数
AES_KEY_SIZE = 32  # 256 bits
AES_NONCE_SIZE = 12  # 96 bits for GCM
AES_TAG_SIZE = 16  # 128 bits GCM auth tag


def generate_rsa_keypair() -> tuple[str, str]:
    """生成 RSA-2048 密钥对，返回 (private_pem, public_pem)"""
    key = RSA.generate(RSA_KEY_SIZE)
    private_pem = key.export_key(format="PEM").decode()
    public_pem = key.public_key().export_key(format="PEM").decode()
    return private_pem, public_pem


def _ensure_keys_exist(
    private_path: str = "rsa_key.pem",
    public_path: str = "rsa_key.pub.pem",
) -> tuple[str, str]:
    """确保密钥文件存在，不存在则自动生成"""
    if os.path.exists(private_path) and os.path.exists(public_path):
        private_pem = Path(private_path).read_text()
        public_pem = Path(public_path).read_text()
    else:
        private_pem, public_pem = generate_rsa_keypair()
        Path(private_path).write_text(private_pem)
        Path(public_path).write_text(public_pem)
    return private_pem, public_pem


def load_private_key(pem: str) -> RSA.RsaKey:
    """从 PEM 字符串加载私钥"""
    return RSA.import_key(pem)


def load_public_key(pem: str) -> RSA.RsaKey:
    """从 PEM 字符串加载公钥"""
    return RSA.import_key(pem)


def encrypt_hybrid(data: dict, public_key_pem: str) -> str:
    """混合加密：AES-GCM 加密数据，RSA-OAEP 加密 AES 密钥

    Args:
        data: 要加密的字典数据
        public_key_pem: RSA 公钥 PEM 字符串

    Returns:
        Base64 编码的密文 (格式: nonce + encrypted_key + tag + ciphertext)
    """
    public_key = load_public_key(public_key_pem)
    rsa_cipher = PKCS1_OAEP.new(public_key, hashAlgo=SHA256)

    # 1. 生成随机 AES 密钥
    aes_key = get_random_bytes(AES_KEY_SIZE)
    nonce = get_random_bytes(AES_NONCE_SIZE)

    # 2. 用 AES-GCM 加密数据
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    aes_cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = aes_cipher.encrypt_and_digest(plaintext)

    # 3. 用 RSA 加密 AES 密钥
    encrypted_key = rsa_cipher.encrypt(aes_key)

    # 4. 拼接: nonce + encrypted_key + tag + ciphertext → Base64
    blob = nonce + encrypted_key + tag + ciphertext
    return base64.b64encode(blob).decode("ascii")


def decrypt_hybrid(encrypted: str, private_key_pem: str) -> dict:
    """混合解密

    Args:
        encrypted: Base64 编码的密文
        private_key_pem: RSA 私钥 PEM 字符串

    Returns:
        解密后的字典
    """
    private_key = load_private_key(private_key_pem)
    rsa_cipher = PKCS1_OAEP.new(private_key, hashAlgo=SHA256)

    # 1. Base64 解码
    blob = base64.b64decode(encrypted)

    # 2. 拆分各部分
    # nonce(12) + encrypted_key(256) + tag(16) + ciphertext(rest)
    encrypted_key_size = RSA_KEY_SIZE // 8  # 2048 bits = 256 bytes

    nonce = blob[:AES_NONCE_SIZE]
    offset = AES_NONCE_SIZE
    encrypted_key = blob[offset : offset + encrypted_key_size]
    offset += encrypted_key_size
    tag = blob[offset : offset + AES_TAG_SIZE]
    offset += AES_TAG_SIZE
    ciphertext = blob[offset:]

    # 3. RSA 解密 AES 密钥
    aes_key = rsa_cipher.decrypt(encrypted_key)

    # 4. AES-GCM 解密
    aes_cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
    plaintext = aes_cipher.decrypt_and_verify(ciphertext, tag)

    return json.loads(plaintext.decode("utf-8"))


# 向后兼容：保留旧的 hash_password 接口
def hash_password(password: str, salt: str) -> str:
    """密码加密 — 超星使用明文传输，预留接口"""
    return password
