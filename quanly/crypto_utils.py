# quanly/crypto_utils.py
import json
import os
from base64 import urlsafe_b64encode, urlsafe_b64decode
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
import pyshamir

def generate_threshold_keys(num_members, threshold):
    """
    Tạo một cặp khóa RSA và chia nhỏ khóa bí mật bằng thuật toán Shamir's Secret Sharing.
    """
    # 1. Tạo một cặp khóa RSA để mã hóa
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    private_key_pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # 2. Chia nhỏ khóa bí mật (dạng bytes) thành các mảnh
    # --- SỬA LỖI Ở ĐÂY: pyshamir.split trả về một danh sách các bytes ---
    shares_bytes_list = pyshamir.split(private_key_pem_bytes, num_members, threshold)
    
    # Chuyển đổi mỗi mảnh (bytes) thành chuỗi Base64 để có thể lưu trữ
    shares_str = [urlsafe_b64encode(share).decode('ascii') for share in shares_bytes_list]
    
    return public_key_pem, shares_str

def encrypt_vote(public_key_pem: str, candidate_ids: list) -> str:
    """
    Mã hóa lựa chọn của cử tri bằng khóa công khai RSA của Hội đồng.
    """
    public_key = serialization.load_pem_public_key(
        public_key_pem.encode('utf-8'),
        backend=default_backend()
    )
    
    message_to_encrypt = json.dumps(sorted(candidate_ids))
    
    ciphertext = public_key.encrypt(
        message_to_encrypt.encode('utf-8'),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    return urlsafe_b64encode(ciphertext).decode('utf-8')

def combine_shares_and_decrypt(key_shares_str: list, encrypted_vote_data: str) -> list:
    """
    Kết hợp các mảnh khóa để tái tạo khóa bí mật và giải mã phiếu bầu.
    """
    # 1. Chuyển đổi các chuỗi mảnh khóa Base64 về lại dạng bytes
    # --- SỬA LỖI Ở ĐÂY: Không cần tách index và value ---
    shares_bytes_list = [urlsafe_b64decode(share_str.encode('ascii')) for share_str in key_shares_str]

    # 2. Tái tạo lại khóa bí mật từ các mảnh
    private_key_pem_bytes = pyshamir.combine(shares_bytes_list)
    
    private_key = serialization.load_pem_private_key(
        private_key_pem_bytes,
        password=None,
        backend=default_backend()
    )
    
    # 3. Giải mã dữ liệu
    ciphertext = urlsafe_b64decode(encrypted_vote_data.encode('utf-8'))
    
    decrypted_message = private_key.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    candidate_ids = json.loads(decrypted_message.decode('utf-8'))
    return candidate_ids
