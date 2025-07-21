from django.shortcuts import get_object_or_404, render

from quanly.models import *
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone # Đảm bảo đã import timezone
from django.contrib.auth import logout as auth_logout
from django.db.models import Q
from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode, urlsafe_b64decode
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from django.http import JsonResponse 
import json
from cryptography.hazmat.primitives.asymmetric import padding
# Create your views here.
def user(request):
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, 'userpages/index.html')

def login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not username or not password:
            messages.error(request, 'Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu.')
            return redirect('login')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect('user')
        else:
            messages.error(request, 'Tên đăng nhập hoặc mật khẩu không đúng.')
            return redirect('login')
    else:
        if request.user.is_authenticated:
            return redirect('user')
        return render(request, 'userpages/login.html')
    
def logout(request):
    auth_logout(request)
    messages.info(request, 'Bạn đã đăng xuất.')
    return redirect('login') # Chuyển hướng về trang đăng nhậpn
# views.py
def ds_baucu(request):
    keyword = request.GET.get('keyword', '')
    
    all_ballots = Ballot.objects.all()

    if keyword:
        all_ballots = all_ballots.filter(
            Q(title__icontains=keyword) | Q(description__icontains=keyword)
        )
    
    now = timezone.now() # Lấy thời gian hiện tại
    active_or_upcoming_ballots = all_ballots.filter(end_date__gte=now).order_by('start_date')

    paginator = Paginator(active_or_upcoming_ballots, 9) 
    page = request.GET.get('page')

    try:
        baucus = paginator.page(page)
    except PageNotAnInteger:
        baucus = paginator.page(1)
    except EmptyPage:
        baucus = paginator.page(paginator.num_pages)

    context = {
        'baucus': baucus,        
        'keyword': keyword,      
        'now': now, # THÊM DÒNG NÀY: Truyền biến 'now' vào context
    }
    
    return render(request, 'userpages/baucu/baucu.html', context)

def chitiet_baucu_u(request, id):
    """
    Hiển thị trang chi tiết và cho phép người dùng bỏ phiếu.
    """
    ballot = get_object_or_404(Ballot, pk=id)
    candidates = Candidate.objects.filter(ballot=ballot)
    
    # Các biến kiểm tra trạng thái để truyền qua template
    now = timezone.now()
    is_active = ballot.start_date <= now <= ballot.end_date
    has_voted = False
    is_voter = hasattr(request.user, 'voter') # Kiểm tra xem user đã đăng ký làm cử tri chưa

    if is_voter:
        # Kiểm tra xem cử tri này đã bỏ phiếu trong cuộc bầu cử này chưa
        has_voted = Vote.objects.filter(
            ballot=ballot, 
            voter_public_key=request.user.voter.public_key
        ).exists()

    context = {
        'baucu': ballot,
        'ungcuviens': candidates,
        'is_active': is_active,
        'has_voted': has_voted,
        'is_voter': is_voter,
    }
    return render(request, 'userpages/baucu/chitiet.html', context)

def view_dangky_cutri(request):
    return render(request, 'userpages/dangky_cutri.html')

def strip_pem_headers(pem_str):
    """Loại bỏ BEGIN/END và khoảng trắng dư"""
    lines = pem_str.strip().splitlines()
    lines = [line for line in lines if not line.startswith("-----")]
    return ''.join(lines)

def dangky_cutri(request):
    if hasattr(request.user, 'voter'):
        messages.warning(request, 'Tài khoản của bạn đã được đăng ký làm cử tri.')
        return redirect('baucu_u')

    if request.method == 'POST':
        password_for_key_encryption = request.POST.get('password_for_key_encryption')
        password_confirm = request.POST.get('password_for_key_encryption_confirm')
        
        if not password_for_key_encryption or not password_confirm:
            messages.error(request, 'Vui lòng nhập mật khẩu mã hóa khóa và xác nhận.')
            # Sử dụng return render để hiển thị lại form với lỗi nếu muốn, hoặc redirect
            return redirect('view_dangky_cutri') 
        
        if password_for_key_encryption != password_confirm:
            messages.error(request, 'Mật khẩu mã hóa khóa không khớp. Vui lòng thử lại.')
            return redirect('view_dangky_cutri')

        try:
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            private_pem_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_key = private_key.public_key()
            public_pem_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )

            public_base64 = strip_pem_headers(public_pem_bytes.decode('utf-8'))
            
            salt = os.urandom(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480000,
                backend=default_backend()
            )
            derived_key_for_fernet = urlsafe_b64encode(kdf.derive(password_for_key_encryption.encode('utf-8')))
            
            f = Fernet(derived_key_for_fernet)
            encrypted_private_key_data = f.encrypt(private_pem_bytes)

            Voter.objects.create(
                user=request.user,
                public_key=public_base64,
            )

            key_data_for_download = {
                "public_key": public_base64,
                "private_key_encrypted": urlsafe_b64encode(encrypted_private_key_data).decode('utf-8'),
                "salt": urlsafe_b64encode(salt).decode('utf-8'),
                "user_id": request.user.id,
                "username": request.user.username,
                "created_at": timezone.now().isoformat(),
                "encryption_method": "AES-256-GCM-Fernet-PBKDF2HMAC"
            }
            


            return JsonResponse({
                'success': True,
                'message': 'Đăng ký cử tri thành công! File khóa của bạn sẽ được tải xuống. Vui lòng lưu trữ nó an toàn.',
                'key_data': key_data_for_download,
                'username': request.user.username,
                'timestamp_str': timezone.now().strftime('%Y%m%d%H%M%S'),
                'redirect_url': '/user/baucu/' # URL bạn muốn chuyển hướng đến sau khi tải file
            })

        except Exception as e:
            # Gửi lỗi qua JSON để JS xử lý
            return JsonResponse({
                'success': False,
                'message': f'Đã có lỗi xảy ra khi sinh khóa: {e}',
                'error_detail': str(e)
            }, status=400) # Gửi mã trạng thái HTTP 400 Bad Request nếu lỗi

    # Với GET request, hiển thị form như bình thường
    return render(request, 'userpages/dangky_cutri.html')

# Cập nhật dangky_cutri_success để hiển thị khóa đúng định dạng
def dangky_cutri_success(request):
    public_key = request.session.pop('newly_generated_public_key', None)
    private_key_pem = request.session.pop('newly_generated_private_key', None) # Lấy PEM gốc
    
    if not public_key or not private_key_pem:
        messages.error(request, "Không tìm thấy thông tin khóa. Vui lòng đăng ký lại.")
        return redirect('user') # Hoặc trang đăng ký

    context = {
        'public_key': public_key,
        'private_key_pem': private_key_pem, # Truyền PEM gốc để hiển thị/tải xuống
    }
    return render(request, 'userpages/dangky_cutri_success.html', context)

from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

def _check_vote_eligibility(request, ballot, voter):
    """
    Kiểm tra các điều kiện cơ bản để người dùng có thể bỏ phiếu trong một cuộc bầu cử.
    - Thời gian bầu cử hợp lệ.
    - Cử tri chưa bỏ phiếu trong cuộc bầu cử này.
    - Cử tri đã được đăng ký và (tùy chọn) được phê duyệt.
    
    Args:
        request: HttpRequest object.
        ballot (Ballot): Đối tượng cuộc bầu cử.
        voter (Voter): Đối tượng cử tri của người dùng hiện tại.

    Returns:
        None: Nếu cử tri đủ điều kiện để bỏ phiếu.
        HttpResponseRedirect: Nếu cử tri không đủ điều kiện, kèm theo thông báo lỗi.
    """
    now = timezone.now()

    # Kiểm tra thời gian bầu cử
    if not (ballot.start_date <= now <= ballot.end_date):
        messages.error(request, 'Cuộc bầu cử này không còn hiệu lực.')
        return redirect('chitiet_baucu_u', id=ballot.id)

    # Kiểm tra cử tri đã bỏ phiếu trong cuộc bầu cử này chưa
    if Vote.objects.filter(ballot=ballot, voter_public_key=voter.public_key).exists():
        messages.warning(request, 'Bạn đã bỏ phiếu trong cuộc bầu cử này rồi.')
        return redirect('chitiet_baucu_u', id=ballot.id)
    
    # [TÙY CHỌN] Kiểm tra nếu bạn có trường `is_approved` trong Voter model
    # if hasattr(voter, 'is_approved') and not voter.is_approved:
    #     messages.error(request, 'Tài khoản của bạn chưa được phê duyệt làm cử tri.')
    #     return redirect('some_approval_status_page') # Chuyển hướng đến trang trạng thái phê duyệt

    return None # Cử tri đủ điều kiện để bỏ phiếu


def _decrypt_private_key_from_strings(encrypted_private_key_b64: str, salt_b64: str, password_for_decryption: str):
    """
    Giải mã private key từ các chuỗi Base64 của private_key_encrypted và salt, cùng với mật khẩu.
    Phương pháp này được dùng khi khóa bí mật được lưu trong file JSON và mã hóa bằng mật khẩu người dùng.
    
    Args:
        encrypted_private_key_b64 (str): Chuỗi Base64 của private key đã mã hóa.
        salt_b64 (str): Chuỗi Base64 của salt.
        password_for_decryption (str): Mật khẩu do người dùng cung cấp để giải mã.

    Returns:
        cryptography.hazmat.primitives.asymmetric.rsa.RSAPrivateNumbers: Đối tượng private key đã giải mã.

    Raises:
        ValueError: Nếu thông tin đầu vào thiếu, mật khẩu sai, hoặc lỗi giải mã.
    """
    if not encrypted_private_key_b64 or not salt_b64 or not password_for_decryption:
        raise ValueError('Thông tin khóa bí mật, salt hoặc mật khẩu giải mã bị thiếu.')
    
    # Chuyển đổi Base64 strings về bytes
    salt_bytes = urlsafe_b64decode(salt_b64.encode('utf-8'))
    password_bytes = password_for_decryption.encode('utf-8')

    # Dẫn xuất khóa đối xứng từ mật khẩu và salt (PBKDF2HMAC)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32, # Độ dài khóa AES-256 (32 bytes = 256 bits)
        salt=salt_bytes,
        iterations=480000, # Số vòng lặp phải khớp CHÍNH XÁC với lúc mã hóa
        backend=default_backend()
    )
    # Khóa đối xứng dùng cho Fernet
    derived_key_for_fernet = urlsafe_b64encode(kdf.derive(password_bytes))
    
    f = Fernet(derived_key_for_fernet)
    
    # Thử giải mã private key
    try:
        decrypted_private_key_pem_bytes = f.decrypt(urlsafe_b64decode(encrypted_private_key_b64.encode('utf-8')))
    except Exception: # Bắt mọi lỗi giải mã Fernet (ví dụ: mật khẩu sai, dữ liệu bị hỏng)
        raise ValueError('Mật khẩu giải mã khóa không đúng hoặc dữ liệu khóa bị lỗi.')
    
    # Tải private key từ định dạng PEM bytes
    private_key = serialization.load_pem_private_key(
        decrypted_private_key_pem_bytes,
        password=None, # Private key PEM không có mật khẩu riêng, đã được Fernet bảo vệ
        backend=default_backend()
    )
    return private_key


def _sign_vote_data(private_key, ballot_id: int, candidate_id: int, voter_public_key: str, timestamp_signed_at: str) -> str:
    """
    Ký dữ liệu phiếu bầu bằng private key.
    
    Args:
        private_key: Đối tượng private key của cryptography.
        ballot_id (int): ID của cuộc bầu cử.
        candidate_id (int): ID của ứng cử viên.
        voter_public_key (str): Khóa công khai của cử tri (Base64).
        timestamp_signed_at (str): Thời gian ký (ISO format).

    Returns:
        str: Chữ ký số đã được mã hóa Base64 URL safe.
    """
    # Dữ liệu cần ký (phải nhất quán giữa ký và xác minh)
    # Bao gồm các thông tin quan trọng để định danh phiếu bầu.
    data_to_be_signed_raw = f"{ballot_id}-{candidate_id}-{voter_public_key}-{timestamp_signed_at}"
    
    # Băm dữ liệu trước khi ký (RSA/ECC thường ký băm của dữ liệu)
    data_to_be_signed_hash = hashlib.sha256(data_to_be_signed_raw.encode('utf-8')).digest()

    # Ký dữ liệu đã băm
    signature = private_key.sign(
        data_to_be_signed_hash,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH # Salt length phải khớp CHÍNH XÁC với lúc xác minh
        ),
        hashes.SHA256() # Thuật toán băm dùng cho chữ ký
    )
    # Chuyển đổi chữ ký từ bytes sang Base64 để lưu trữ/truyền tải
    return urlsafe_b64encode(signature).decode('utf-8')


def _verify_signature_internal(public_key_str: str, data_to_be_signed_raw: str, signature_b64: str) -> bool:
    """
    Xác minh chữ ký số bằng public key.
    Đây là bước kiểm tra nội bộ sau khi ký (hoặc có thể dùng cho kiểm toán sau này).
    
    Args:
        public_key_str (str): Khóa công khai của người ký (Base64).
        data_to_be_signed_raw (str): Dữ liệu gốc (chưa băm) đã được ký.
        signature_b64 (str): Chữ ký số đã được mã hóa Base64.

    Returns:
        bool: True nếu chữ ký hợp lệ, False nếu không hợp lệ.
    """
    try:
        # Chuyển đổi chữ ký từ Base64 sang bytes
        signature_bytes = urlsafe_b64decode(signature_b64.encode('utf-8'))
        
        # Tái tạo băm của dữ liệu gốc
        data_to_be_signed_hash = hashlib.sha256(data_to_be_signed_raw.encode('utf-8')).digest()

        # Tải public key từ chuỗi Base64
        # Public key được lưu là Base64 của SubjectPublicKeyInfo PEM, cần thêm header/footer lại
        public_pem_with_headers = f"-----BEGIN PUBLIC KEY-----\n{public_key_str}\n-----END PUBLIC KEY-----"
        public_key = serialization.load_pem_public_key(
            public_pem_with_headers.encode('utf-8'),
            backend=default_backend()
        )

        # Thực hiện xác minh chữ ký
        public_key.verify(
            signature_bytes,
            data_to_be_signed_hash,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH # Salt length phải khớp CHÍNH XÁC với lúc ký
            ),
            hashes.SHA256() # Thuật toán băm dùng cho chữ ký
        )
        return True # Nếu không có lỗi, chữ ký hợp lệ
    except Exception as e:
        print(f"Lỗi xác minh chữ ký: {e}") # Ghi log lỗi để debug
        return False


def bo_phieu(request, id):
    if request.method == 'POST':
        try:
            ballot = get_object_or_404(Ballot, pk=id)
            
            if not hasattr(request.user, 'voter'):
                 messages.error(request, 'Bạn cần đăng ký làm cử tri để bỏ phiếu.')
                 return redirect('view_dangky_cutri')
            voter = request.user.voter # Lấy Voter object để có public_key (từ DB)

            eligibility_check_result = _check_vote_eligibility(request, ballot, voter)
            if eligibility_check_result:
                return eligibility_check_result

            candidate_id = request.POST.get('candidate')
            if not candidate_id:
                messages.error(request, 'Bạn chưa chọn ứng cử viên.')
                return redirect('chitiet_baucu_u', id=ballot.id)
            candidate = get_object_or_404(Candidate, pk=candidate_id, ballot=ballot)

            password_for_key_decryption = request.POST.get('password_for_key_decryption')
            if not password_for_key_decryption:
                messages.error(request, 'Vui lòng nhập mật khẩu để giải mã khóa.')
                return redirect('chitiet_baucu_u', id=ballot.id)

            private_key = None
            input_public_key_str = None # Biến để lưu public key từ input/file

            # Xác định người dùng đã chọn cách nào để cung cấp khóa
            if 'key_file' in request.FILES and request.FILES['key_file']:
                # Cách 1: Tải file JSON
                key_file = request.FILES['key_file']
                file_content = key_file.read().decode('utf-8')
                key_data = json.loads(file_content)

                encrypted_private_key_b64 = key_data.get('private_key_encrypted')
                salt_b64 = key_data.get('salt')
                input_public_key_str = key_data.get('public_key') # Lấy public key từ file

                if not encrypted_private_key_b64 or not salt_b64 or not input_public_key_str:
                    messages.error(request, 'File khóa không hợp lệ hoặc bị thiếu thông tin.')
                    return redirect('chitiet_baucu_u', id=ballot.id)

                # Kiểm tra public key từ file có khớp với public key của người dùng trong DB không
                if input_public_key_str != voter.public_key:
                    messages.error(request, 'Khóa công khai trong file không khớp với tài khoản của bạn. Vui lòng kiểm tra lại.')
                    return redirect('chitiet_baucu_u', id=ballot.id)

                # Giải mã private key từ các chuỗi lấy từ file
                private_key = _decrypt_private_key_from_strings(
                    encrypted_private_key_b64, salt_b64, password_for_key_decryption
                )

            elif request.POST.get('private_key_encrypted') and request.POST.get('salt') and request.POST.get('public_key'):
                # Cách 2: Dán chuỗi trực tiếp
                encrypted_private_key_b64 = request.POST.get('private_key_encrypted')
                salt_b64 = request.POST.get('salt')
                input_public_key_str = request.POST.get('public_key') # Lấy public key từ input

                if not encrypted_private_key_b64 or not salt_b64 or not input_public_key_str:
                    messages.error(request, 'Vui lòng điền đầy đủ thông tin khóa bí mật, salt và public key.')
                    return redirect('chitiet_baucu_u', id=ballot.id)

                # Kiểm tra public key từ input có khớp với public key của người dùng trong DB không
                if input_public_key_str != voter.public_key:
                    messages.error(request, 'Khóa công khai đã nhập không khớp với tài khoản của bạn. Vui lòng kiểm tra lại.')
                    return redirect('chitiet_baucu_u', id=ballot.id)

                # Giải mã private key từ các chuỗi lấy từ input
                private_key = _decrypt_private_key_from_strings(
                    encrypted_private_key_b64, salt_b64, password_for_key_decryption
                )

            else:
                messages.error(request, 'Vui lòng cung cấp khóa bí mật bằng cách tải file hoặc dán chuỗi.')
                return redirect('chitiet_baucu_u', id=ballot.id)
            
            # Nếu đến đây mà private_key vẫn là None, có nghĩa là có lỗi trong quá trình decrypt
            # (Hoặc lỗi không bắt được trong try-except của _decrypt_private_key_from_strings)
            if private_key is None:
                messages.error(request, 'Không thể giải mã khóa bí mật. Vui lòng kiểm tra lại dữ liệu khóa và mật khẩu.')
                return redirect('chitiet_baucu_u', id=ballot.id)

            timestamp_signed_at = timezone.now().isoformat()

            # Ký dữ liệu phiếu bầu
            signed_signature_b64 = _sign_vote_data(
                private_key, 
                ballot.id, 
                candidate.id, 
                voter.public_key, # Luôn dùng public_key từ DB để ký data
                timestamp_signed_at
            )

            # Xác minh chữ ký ngay sau khi ký (kiểm tra tính đúng đắn của quá trình ký)
            is_verified_internally = _verify_signature_internal(
                voter.public_key, # Luôn dùng public_key từ DB để xác minh
                f"{ballot.id}-{candidate.id}-{voter.public_key}-{timestamp_signed_at}", # Dữ liệu gốc đã ký
                signed_signature_b64
            )
            if not is_verified_internally:
                messages.error(request, 'Lỗi xác minh nội bộ sau khi ký. Phiếu bầu bị từ chối.')
                return redirect('chitiet_baucu_u', id=ballot.id)

            # Lưu phiếu bầu vào database
            vote = Vote.objects.create( # Tạo đối tượng vote
                ballot=ballot,
                candidate=candidate,
                voter_public_key=voter.public_key,
                signature=signed_signature_b64,
                timestamp=timestamp_signed_at
            )
            # vote_hash sẽ tự động được tính toán trong hàm save() của Vote model

            messages.success(request, 'Bỏ phiếu thành công và đã được xác minh bằng chữ ký số!')
            return redirect('chitiet_baucu_u', id=ballot.id)

        except json.JSONDecodeError:
            messages.error(request, 'File khóa không phải là định dạng JSON hợp lệ.')
            return redirect('chitiet_baucu_u', id=ballot.id)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('chitiet_baucu_u', id=ballot.id)
        except Exception as e:
            messages.error(request, f'Lỗi hệ thống khi bỏ phiếu: {e}')
            return redirect('chitiet_baucu_u', id=ballot.id)

    return redirect('chitiet_baucu_u', id=id)