from django.shortcuts import get_object_or_404, render

from quanly.blockchain_utils import *

from quanly.models import *
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.primitives import serialization
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone 
from django.contrib.auth import logout as auth_logout
from django.db.models import Q
from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode, urlsafe_b64decode
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from django.http import JsonResponse 
import json
from django.db.models import Count
from cryptography.hazmat.primitives.asymmetric import padding

from django.db import transaction
from django.conf import settings
from .user_utils import (
    strip_pem_headers,
    _check_vote_eligibility,
    _decrypt_private_key_from_strings, 
    _sign_vote_data,
    _verify_signature_internal
)


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
    return redirect('login')


def ds_baucu(request):

    keyword = request.GET.get('keyword', '')
    current_filter = request.GET.get('filter', 'all')


    visible_ballots = Ballot.objects.filter(type='PUBLIC')

    #  Nếu người dùng đã đăng nhập và là một cử tri
    if request.user.is_authenticated and hasattr(request.user, 'voter'):
        voter = request.user.voter
        private_ballots_for_voter = Ballot.objects.filter(type='PRIVATE', eligible_voters=voter)
        # Kết hợp cả hai queryset
        visible_ballots = visible_ballots | private_ballots_for_voter

    #  Áp dụng bộ lọc từ các tab
    if current_filter == 'public':
        all_ballots = visible_ballots.filter(type='PUBLIC')
    elif current_filter == 'private':
   
        all_ballots = visible_ballots.filter(type='PRIVATE')
    else: 
        all_ballots = visible_ballots


    if keyword:
        all_ballots = all_ballots.filter(
            Q(title__icontains=keyword) | Q(description__icontains=keyword)
        )
    

    all_ballots = all_ballots.distinct().order_by('-start_date')


    paginator = Paginator(all_ballots, 9)
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
        'now': timezone.now(),
        'current_filter': current_filter, 
    }
    
    return render(request, 'userpages/baucu/baucu.html', context)

def chitiet_baucu_u(request, id):

    ballot = get_object_or_404(Ballot, pk=id)
    candidates = Candidate.objects.filter(ballot=ballot)
    
    # Các biến kiểm tra trạng thái
    now = timezone.now()
    is_active = ballot.start_date <= now <= ballot.end_date
    is_ended = now > ballot.end_date 
    has_voted = False
    is_voter = hasattr(request.user, 'voter')
    winners = [] 

    if is_voter:
        has_voted = Vote.objects.filter(
            ballot=ballot, 
            voter_public_key=request.user.voter.public_key
        ).exists()


    if is_ended:
        # Đếm số phiếu cho mỗi ứng viên
        results = Vote.objects.filter(ballot=ballot)\
            .values('candidate')\
            .annotate(vote_count=Count('id'))\
            .order_by('-vote_count')

        # Nếu có kết quả
        if results:
            # Lấy số phiếu cao nhất
            max_votes = results[0]['vote_count']
            # Tìm tất cả các ứng viên có số phiếu bằng số phiếu cao nhất (xử lý trường hợp hòa)
            winner_ids = [r['candidate'] for r in results if r['vote_count'] == max_votes]
            winners = Candidate.objects.filter(id__in=winner_ids)


    context = {
        'baucu': ballot,
        'ungcuviens': candidates,
        'is_active': is_active,
        'has_voted': has_voted,
        'is_voter': is_voter,
        'is_ended': is_ended,  
        'winners': winners,    
    }
    return render(request, 'userpages/baucu/chitiet.html', context)

def view_dangky_cutri(request):
    return render(request, 'userpages/dangky_cutri.html')

def strip_pem_headers(pem_str):

    lines = pem_str.strip().splitlines()
    lines = [line for line in lines if not line.startswith("-----")]
    return ''.join(lines)

def dangky_cutri(request):
    if hasattr(request.user, 'voter'):
        messages.warning(request, 'Tài khoản của bạn đã được đăng ký làm cử tri.')
        return redirect('baucu_u') 

    if request.method == 'POST':

        try:
            # private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            private_key = ec.generate_private_key(ec.SECP256R1())
            private_pem_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption()
            )
            public_key = private_key.public_key()
            public_pem_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            public_base64 = strip_pem_headers(public_pem_bytes.decode('utf-8'))
            

            
            Voter.objects.create(user=request.user, public_key=public_base64)
            
            key_data_for_download = {
                "public_key": public_base64, 
                "private_key_pem_b64": urlsafe_b64encode(private_pem_bytes).decode('utf-8'), # LƯU PRIVATE KEY PLAINTEXT (BASE64)
                "user_id": request.user.id, "username": request.user.username,
                "created_at": timezone.now().isoformat(), 
                "encryption_method": "NONE" # Ghi chú rằng không có mã hóa
            }
            
            return JsonResponse({
                'success': True, 'message': 'Đăng ký cử tri thành công! File khóa của bạn sẽ được tải xuống. Vui lòng lưu trữ nó an toàn.',
                'key_data': key_data_for_download, 'username': request.user.username,
                'timestamp_str': timezone.now().strftime('%Y%m%d%H%M%S'), 'redirect_url': '/user/baucu/' 
            })

        except Exception as e:
            return JsonResponse({
                'success': False, 'message': f'Đã có lỗi xảy ra khi sinh khóa: {e}', 'error_detail': str(e)
            }, status=400)
    
    return render(request, 'userpages/dangky_cutri.html')



from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

def _check_vote_eligibility(request, ballot, voter):
  
    now = timezone.now()

    # Kiểm tra thời gian bầu cử
    if not (ballot.start_date <= now <= ballot.end_date):
        messages.error(request, 'Cuộc bầu cử này không còn hiệu lực.')
        return redirect('chitiet_baucu_u', id=ballot.id)

    # Kiểm tra cử tri đã bỏ phiếu trong cuộc bầu cử này chưa
    if Vote.objects.filter(ballot=ballot, voter_public_key=voter.public_key).exists():
        messages.warning(request, 'Bạn đã bỏ phiếu trong cuộc bầu cử này rồi.')
        return redirect('chitiet_baucu_u', id=ballot.id)
    

    return None 




def my_vote(request, id):
    ballot = get_object_or_404(Ballot, pk=id)
    
    if not hasattr(request.user, 'voter'):
        messages.error(request, "Bạn không phải là cử tri.")
        return redirect('chitiet_baucu_u', id=id)

    # Lấy thời gian hiện tại
    now = timezone.now()
    is_ended = now > ballot.end_date

    try:
        # Tìm phiếu bầu 
        my_vote = Vote.objects.get(ballot=ballot, voter_public_key=request.user.voter.public_key)
        is_in_block = my_vote.block is not None
    except Vote.DoesNotExist:
        my_vote = None
        is_in_block = False

    context = {
        'baucu': ballot,
        'my_vote': my_vote,
        'is_in_block': is_in_block,
        'is_ended': is_ended, 
    }
    return render(request, 'userpages/baucu/my_vote.html', context)

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

# def change_vote(request, vote_id):

#     vote = get_object_or_404(Vote, pk=vote_id)

#     # Đảm bảo chỉ chính chủ mới có thể truy cập
#     if not hasattr(request.user, 'voter') or vote.voter_public_key != request.user.voter.public_key:
#         messages.error(request, "Bạn không có quyền truy cập phiếu bầu này.")
#         return redirect('baucu_u')

#     if request.method == 'POST':
#         new_candidate_id = request.POST.get('candidate')
#         if not new_candidate_id:
#             messages.warning(request, "Bạn chưa chọn ứng viên mới.")
#             return redirect('change_vote', vote_id=vote.id)

#         new_candidate = get_object_or_404(Candidate, pk=new_candidate_id, ballot=vote.ballot)

#         # TRƯỜNG HỢP PHIẾU CHƯA BỊ NIÊM PHONG 
#         if vote.block is None:
#             vote.candidate = new_candidate
#             vote.save() 
#             messages.success(request, "Thay đổi phiếu bầu thành công vì phiếu chưa được niêm phong.")
#             return redirect('my_vote', id=vote.ballot.id)
        
#         # 2 TRƯỜNG HỢP PHIẾU ĐÃ BỊ NIÊM PHONG 
#         else:
#             client_ip = get_client_ip(request) 
#             user_agent = request.user_agent
#             # Lấy vị trí
#             latitude_val = request.POST.get('latitude')
#             longitude_val = request.POST.get('longitude')
#             latitude = float(latitude_val) if latitude_val else None
#             longitude = float(longitude_val) if longitude_val else None

#             # Ghi log lại hành vi, bao gồm cả IP
#             UserTamperLog.objects.create(
#                 attempted_by=request.user,
#                 vote_tampered=vote,
#                 original_candidate_name=vote.candidate.name,
#                 new_candidate_name_attempt=new_candidate.name,
#                 description=f" Thay đổi phiếu bầu đã bị niêm phong.",
#                 ip_address=client_ip,
#                 browser=f"{user_agent.browser.family} {user_agent.browser.version_string}",
#                 os=f"{user_agent.os.family} {user_agent.os.version_string}",
#                 device=f"{user_agent.device.family}",
#                 latitude=latitude,  
#                 longitude=longitude, 
#             )
            
#             # Đưa ra cảnh báo nghiêm trọng
#             messages.error(
#                 request, 
#                 "Bạn không thể thay đổi một phiếu bầu đã được niêm phong vào blockchain. Hành vi cố gắng thay đổi của bạn đã được hệ thống ghi lại."
#                     )
#             return redirect('my_vote', id=vote.ballot.id)

#     candidates = Candidate.objects.filter(ballot=vote.ballot)
#     context = {
#         'vote': vote,
#         'candidates': candidates,
#     }
#     return render(request, 'userpages/baucu/change_vote.html', context)


def bo_phieu(request, id):
    """
    View xử lý việc bỏ phiếu với quy trình an ninh đầy đủ:
    Kiểm tra -> (Nếu lỗi: Log, Phục hồi) -> Xác thực -> Ký -> Đào khối -> Cập nhật -> Backup.
    """
    if request.method != 'POST':
        return redirect('chitiet_baucu_u', id=id)

    ballot = get_object_or_404(Ballot, pk=id)
    blockchain_export_dir = os.path.join(settings.BASE_DIR, 'quanly', 'save_blockchain')
    file_path = get_blockchain_file_path(ballot.id, blockchain_export_dir)

    # --- BƯỚC 1: KIỂM TRA TÍNH TOÀN VẸN CỦA SỔ CÁI TRƯỚC KHI XỬ LÝ ---
    if os.path.exists(file_path):
        is_valid, verify_msg = verify_blockchain_integrity(ballot.id, blockchain_export_dir)
        if not is_valid:
            # 1. Backup lại file đã bị thay đổi để điều tra
            tampered_backup_path = backup_tampered_file(ballot.id, blockchain_export_dir)
            
            # 2. Ghi log sự cố vào CSDL
            log_tampering_event(
                ballot=ballot,
                verify_msg=verify_msg,
                user=request.user,
                ip_address=get_client_ip(request),
                backup_path=tampered_backup_path
            )
            
            # 3. Phục hồi từ bản sao lưu an toàn cuối cùng
            restored = restore_from_backup(ballot.id, blockchain_export_dir)
            if restored:
                messages.warning(request, "CẢNH BÁO: Sổ cái đã bị thay đổi! Hệ thống đã tự động phục hồi. Giao dịch của bạn sẽ được xử lý.")
            else:
                messages.error(request, "LỖI BẢO MẬT: Sổ cái đã bị thay đổi và không có bản sao lưu để phục hồi. Vui lòng liên hệ quản trị viên.")
                return redirect('chitiet_baucu_u', id=id)

    # --- Nếu file an toàn hoặc đã được phục hồi, tiếp tục quy trình ---
    try:
        with transaction.atomic():
            # --- Giai đoạn 2: Xác thực quyền và dữ liệu của người dùng ---
            if not hasattr(request.user, 'voter'):
                messages.error(request, 'Bạn cần đăng ký làm cử tri để bỏ phiếu.')
                return redirect('chitiet_baucu_u', id=id)
            voter = request.user.voter
            
            eligibility = _check_vote_eligibility(request, ballot, voter)
            if eligibility:
                return eligibility

            candidate_id = request.POST.get('candidate')
            if not candidate_id:
                messages.error(request, 'Bạn chưa chọn ứng cử viên.')
                return redirect('chitiet_baucu_u', id=ballot.id)
            
            candidate = get_object_or_404(Candidate, pk=candidate_id, ballot=ballot)

            # Xử lý file khóa
            private_key = None
            if 'key_file' in request.FILES and request.FILES['key_file']:
                key_file = request.FILES['key_file']
                key_data = json.loads(key_file.read().decode('utf-8'))
                private_key_pem_b64 = key_data.get('private_key_pem_b64')
                input_public_key_str = key_data.get('public_key')
                
                if not private_key_pem_b64 or not input_public_key_str or input_public_key_str != voter.public_key:
                    messages.error(request, 'File khóa không hợp lệ hoặc không khớp với tài khoản của bạn.')
                    return redirect('chitiet_baucu_u', id=id)
                    
                private_key = _decrypt_private_key_from_strings(private_key_pem_b64, input_public_key_str)
            else:
                messages.error(request, 'Vui lòng tải lên file khóa của bạn.')
                return redirect('chitiet_baucu_u', id=id)

            if private_key is None: 
                messages.error(request, 'Không thể tải khóa bí mật. Vui lòng kiểm tra lại dữ liệu khóa.')
                return redirect('chitiet_baucu_u', id=id)

            # --- Giai đoạn 3: Ký và Xác minh chữ ký ---
            timestamp_signed_at = timezone.now().isoformat()
            data_to_sign = f"{ballot.id}-{candidate.id}-{voter.public_key}-{timestamp_signed_at}"
            signed_signature_b64 = _sign_vote_data(private_key, ballot.id, candidate.id, voter.public_key, timestamp_signed_at)
            
            if not _verify_signature_internal(voter.public_key, data_to_sign, signed_signature_b64):
                messages.error(request, 'Lỗi xác minh chữ ký. Phiếu bầu bị từ chối.')
                return redirect('chitiet_baucu_u', id=id)

            # --- Giai đoạn 4: Đào khối và Cập nhật ---
            last_block = Block.objects.filter(ballot=ballot).order_by('-id').first()
            new_block = Block.objects.create(
                ballot=ballot,
                previous_hash=last_block.hash if last_block else '0',
                difficulty=2 
            )
            Vote.objects.create(
                ballot=ballot, candidate=candidate,
                voter_public_key=voter.public_key,
                signature=signed_signature_b64, timestamp=timestamp_signed_at,
                block=new_block
            )
            new_block.mine_block()
            
            # 4.1. Ghi đè file JSON gốc với dữ liệu mới nhất từ CSDL
            success, msg = save_blockchain_to_json_with_integrity_check(ballot.id, base_export_dir=blockchain_export_dir)
            
            if success:
                # 4.2. TẠO BACKUP MỚI cho file vừa được cập nhật
                create_backup(ballot.id, blockchain_export_dir)
                messages.success(request, 'Bỏ phiếu thành công! Sổ cái đã được cập nhật an toàn.')
            else:
                print(f"Lỗi nghiêm trọng khi xuất file JSON sau khi vote: {msg}")
                messages.warning(request, "Bỏ phiếu thành công nhưng có lỗi khi cập nhật sổ cái. Vui lòng liên hệ quản trị viên.")

            return redirect('chitiet_baucu_u', id=id)

    except Exception as e:
        messages.error(request, f'Đã có lỗi xảy ra: {e}')
        return redirect('chitiet_baucu_u', id=id)

    return redirect('chitiet_baucu_u', id=id)
