"""Authentication Token Handler"""

import jwt
import time
import json
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64


class AuthToken:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode()

    def _derive_key(self, length: int) -> bytes:
        """Dẫn xuất khóa có độ dài cố định"""
        # Sử dụng muối cố định (trong môi trường thực tế nên dùng muối ngẫu nhiên)
        salt = b"fixed_salt_placeholder"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=length,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )
        return kdf.derive(self.secret_key)

    def _encrypt_payload(self, payload: dict) -> str:
        """Mã hóa toàn bộ payload bằng AES-GCM"""
        # Dẫn xuất khóa mã hóa (32 byte cho AES-256)
        enc_key = self._derive_key(32)

        # Tạo nonce (96 bit cho GCM)
        import os

        nonce = os.urandom(12)

        # Tạo cipher
        cipher = Cipher(
            algorithms.AES(enc_key),
            modes.GCM(nonce),
            backend=default_backend(),
        )
        encryptor = cipher.encryptor()

        # Mã hóa dữ liệu
        payload_json = json.dumps(payload)
        ciphertext = encryptor.update(payload_json.encode()) + encryptor.finalize()

        # Trả về (nonce + tag + ciphertext) được mã hóa base64
        result = base64.urlsafe_b64encode(nonce + encryptor.tag + ciphertext).decode("utf-8")
        return result

    def _decrypt_payload(self, encrypted_data: str) -> dict:
        """Giải mã payload"""
        # Dẫn xuất khóa mã hóa
        enc_key = self._derive_key(32)

        # Giải mã dữ liệu base64
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())

        # Tách nonce, tag, ciphertext
        nonce = encrypted_bytes[:12]
        tag = encrypted_bytes[12:28]
        ciphertext = encrypted_bytes[28:]

        # Tạo cipher
        cipher = Cipher(
            algorithms.AES(enc_key),
            modes.GCM(nonce, tag),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()

        # Giải mã
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        return json.loads(plaintext.decode())

    def generate_token(self, device_id: str) -> str:
        """
        Tạo JWT token
        :param device_id: ID thiết bị
        :return: Chuỗi JWT token
        """
        # Thiết lập thời gian hết hạn sau 1 giờ
        expire_time = datetime.now(timezone.utc) + timedelta(hours=1)

        # Tạo payload gốc
        payload = {"device_id": device_id, "exp": expire_time.timestamp()}

        # Mã hóa toàn bộ payload
        encrypted_payload = self._encrypt_payload(payload)

        # Tạo payload bên ngoài, chứa dữ liệu đã mã hóa
        outer_payload = {"data": encrypted_payload}

        # Mã hóa bằng JWT
        token = jwt.encode(outer_payload, self.secret_key, algorithm="HS256")
        return token

    def verify_token(self, token: str) -> Tuple[bool, Optional[str]]:
        """
        Xác minh token
        :param token: Chuỗi JWT token
        :return: (Có hợp lệ hay không, ID thiết bị)
        """
        try:
            # Xác minh lớp JWT bên ngoài (chữ ký và thời hạn)
            outer_payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])

            # Giải mã payload bên trong
            inner_payload = self._decrypt_payload(outer_payload["data"])

            # Kiểm tra lại thời hạn (xác minh kép)
            if inner_payload["exp"] < time.time():
                return False, None

            return True, inner_payload["device_id"]

        except jwt.InvalidTokenError:
            return False, None
        except json.JSONDecodeError:
            return False, None
        except Exception as e:
            print(f"Token verification failed: {str(e)}")
            return False, None
