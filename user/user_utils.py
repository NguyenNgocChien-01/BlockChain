# File: user/user_utils.py

from cryptography.hazmat.primitives.asymmetric import padding, rsa, ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC # Vẫn cần nếu bạn muốn quay lại dùng salt/mật khẩu
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet # Vẫn cần nếu bạn muốn quay lại dùng salt/mật khẩu
from cryptography.hazmat.primitives import serialization

from base64 import urlsafe_b64decode, urlsafe_b64encode
import hashlib
import json
from django.utils import timezone
from django.shortcuts import redirect
from django.contrib import messages
# Import models từ app quanly (vì models nằm trong quanly/models.py)
from quanly.models import Ballot, Candidate, Vote, Voter


def strip_pem_headers(pem_str: str) -> str:
    """Loại bỏ BEGIN/END và khoảng trắng dư từ chuỗi PEM."""
    lines = pem_str.strip().splitlines()
    lines = [line for line in lines if not line.startswith("-----")]
    return ''.join(lines)


def _check_vote_eligibility(request, ballot, voter):

    now = timezone.now()
    
    # 1. Kiểm tra thời gian
    if not (ballot.start_date <= now and ballot.end_date >= now):
        messages.error(request, 'Cuộc bầu cử này không còn hiệu lực.')
        return redirect('chitiet_baucu_u', id=ballot.id)

    # 2. Kiểm tra xem đã bỏ phiếu chưa
    if Vote.objects.filter(ballot=ballot, voter_public_key=voter.public_key).exists():
        messages.warning(request, 'Bạn đã bỏ phiếu trong cuộc bầu cử này rồi.')
        return redirect('chitiet_baucu_u', id=ballot.id)
        
    # 3. Nếu là bầu cử riêng tư, kiểm tra xem cử tri có trong danh sách không
    if ballot.type == 'PRIVATE':
        if not ballot.eligible_voters.filter(pk=voter.pk).exists():
            messages.error(request, 'Bạn không có quyền tham gia cuộc bầu cử riêng tư này.')
            return redirect('baucu_u') # Chuyển về trang danh sách chung

    return None # Nếu tất cả đều hợp lệ


def _decrypt_private_key_from_strings(private_key_pem_b64: str, public_key_from_file_str: str):
    """
    Tải private key từ chuỗi Base64 của private_key_pem (không mã hóa).
    """
    if not private_key_pem_b64 or not public_key_from_file_str:
        raise ValueError('Thông tin khóa bí mật hoặc khóa công khai bị thiếu.')
    
    private_pem_bytes = urlsafe_b64decode(private_key_pem_b64.encode('utf-8'))

    try:
        private_key = serialization.load_pem_private_key(
            private_pem_bytes, password=None, backend=default_backend()
        )
    except Exception as e:
        raise ValueError(f'Lỗi khi tải khóa bí mật từ chuỗi: {e}. Chuỗi khóa có thể không hợp lệ.')
    
    public_key_from_file_with_headers = f"-----BEGIN PUBLIC KEY-----\n{public_key_from_file_str}\n-----END PUBLIC KEY-----"
    try:
        loaded_public_key = serialization.load_pem_public_key(public_key_from_file_with_headers.encode('utf-8'), backend=default_backend())
        if private_key.public_key().public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo) != loaded_public_key.public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo):
            raise ValueError("Khóa bí mật và khóa công khai không khớp.")
    except Exception as e:
        raise ValueError(f"Lỗi kiểm tra khớp khóa: {e}. Khóa công khai có thể không hợp lệ.")

    return private_key


def _sign_vote_data(private_key, data_to_sign_raw: str) -> str:
    """
    Ký một chuỗi dữ liệu thô (đã được chuẩn hóa).
    Hàm này giờ đây linh hoạt hơn, không phụ thuộc vào các thành phần riêng lẻ.
    """
    data_to_be_signed_hash = hashlib.sha256(data_to_sign_raw.encode('utf-8')).digest()
    
    # Giả sử bạn đang dùng ECC
    signature = private_key.sign(
        data_to_be_signed_hash,
        ec.ECDSA(hashes.SHA256()) 
    )
    return urlsafe_b64encode(signature).decode('utf-8')


def _verify_signature_internal(public_key_str: str, data_to_sign_raw: str, signature_b64: str) -> bool:
    """
    Xác minh chữ ký của một chuỗi dữ liệu thô.
    """
    try:
        signature_bytes = urlsafe_b64decode(signature_b64.encode('utf-8'))
        data_to_be_signed_hash = hashlib.sha256(data_to_sign_raw.encode('utf-8')).digest()
        
        public_pem_with_headers = f"-----BEGIN PUBLIC KEY-----\n{public_key_str}\n-----END PUBLIC KEY-----\n"
        public_key = serialization.load_pem_public_key(public_pem_with_headers.encode('utf-8'), backend=default_backend())
        
        public_key.verify(
            signature_bytes,
            data_to_be_signed_hash,
            ec.ECDSA(hashes.SHA256())
        )
        return True
    except Exception as e:
        # print(f"Lỗi xác minh chữ ký: {e}") # Bật lại để gỡ lỗi nếu cần
        return False