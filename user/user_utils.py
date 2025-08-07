from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from base64 import urlsafe_b64decode, urlsafe_b64encode
import hashlib
from django.utils import timezone
from django.contrib import messages
from quanly.models import Ballot, Vote, Voter

# ==============================================================================
# === LỚP WALLET: Quản lý các tác vụ Mật mã ===
# ==============================================================================

class Wallet:
    """
    Đóng gói tất cả các hoạt động liên quan đến khóa của một cử tri,
    bao gồm tải khóa, ký và xác minh.
    """
    def __init__(self, private_key_pem_b64: str, public_key_str: str):
        if not private_key_pem_b64 or not public_key_str:
            raise ValueError('Thiếu thông tin khóa bí mật hoặc khóa công khai.')
        
        self.public_key_str = public_key_str
        private_pem_bytes = urlsafe_b64decode(private_key_pem_b64.encode('utf-8'))

        try:
            self.private_key = serialization.load_pem_private_key(
                private_pem_bytes, password=None, backend=default_backend()
            )
            self.public_key = self.private_key.public_key()
        except Exception as e:
            raise ValueError(f'Lỗi khi tải khóa bí mật từ chuỗi: {e}.')

        # Xác minh cặp khóa khớp nhau
        self._verify_key_pair()

    def _verify_key_pair(self):
        """Kiểm tra để đảm bảo khóa bí mật và khóa công khai được cung cấp là một cặp."""
        try:
            public_pem_with_headers = f"-----BEGIN PUBLIC KEY-----\n{self.public_key_str}\n-----END PUBLIC KEY-----\n"
            loaded_public_key = serialization.load_pem_public_key(public_pem_with_headers.encode('utf-8'), backend=default_backend())
            
            if self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM, 
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ) != loaded_public_key.public_bytes(
                encoding=serialization.Encoding.PEM, 
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ):
                raise ValueError("Khóa bí mật và khóa công khai không khớp.")
        except Exception as e:
            raise ValueError(f"Lỗi kiểm tra khớp khóa: {e}.")

    def sign(self, data_to_sign_raw: str) -> str:
        """Ký một chuỗi dữ liệu thô bằng khóa bí mật."""
        data_hash = hashlib.sha256(data_to_sign_raw.encode('utf-8')).digest()
        signature = self.private_key.sign(
            data_hash,
            ec.ECDSA(hashes.SHA256()) 
        )
        return urlsafe_b64encode(signature).decode('utf-8')

    @staticmethod
    def verify(public_key_str: str, data_to_sign_raw: str, signature_b64: str) -> bool:
        """Xác minh một chữ ký bằng khóa công khai (phương thức tĩnh)."""
        try:
            signature_bytes = urlsafe_b64decode(signature_b64.encode('utf-8'))
            data_hash = hashlib.sha256(data_to_sign_raw.encode('utf-8')).digest()
            
            public_pem_with_headers = f"-----BEGIN PUBLIC KEY-----\n{public_key_str}\n-----END PUBLIC KEY-----\n"
            public_key = serialization.load_pem_public_key(public_pem_with_headers.encode('utf-8'), backend=default_backend())
            
            public_key.verify(
                signature_bytes,
                data_hash,
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except Exception:
            return False

# ==============================================================================
# === LỚP VOTEVALIDATOR: Kiểm tra tính hợp lệ của Phiếu bầu ===
# ==============================================================================

class VoteValidator:
    """
    Đóng gói logic kiểm tra xem một cử tri có đủ điều kiện để bỏ phiếu hay không.
    """
    def __init__(self, ballot: Ballot, voter: Voter):
        self.ballot = ballot
        self.voter = voter

    def is_eligible(self) -> (bool, str): # pyright: ignore[reportInvalidTypeForm]
        """
        Thực hiện tất cả các kiểm tra.
        Trả về (True, None) nếu hợp lệ, hoặc (False, "Thông báo lỗi") nếu không.
        """
        # 1. Kiểm tra thời gian
        now = timezone.localtime()
        if not (self.ballot.start_date <= now and self.ballot.end_date >= now):
            return False, 'Cuộc bầu cử này không còn hiệu lực.'

        # 2. Kiểm tra xem đã bỏ phiếu chưa
        if Vote.objects.filter(ballot=self.ballot, voter_public_key=self.voter.public_key).exists():
            return False, 'Bạn đã bỏ phiếu trong cuộc bầu cử này rồi.'
            
        # 3. Nếu là bầu cử riêng tư, kiểm tra xem cử tri có trong danh sách không
        if self.ballot.type == 'PRIVATE':
            if not self.ballot.eligible_voters.filter(pk=self.voter.pk).exists():
                return False, 'Bạn không có quyền tham gia cuộc bầu cử riêng tư này.'

        return True, None # Nếu tất cả đều hợp lệ

# --- CÁC HÀM TIỆN ÍCH KHÁC (NẾU CÓ) ---
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
