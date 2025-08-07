from django.shortcuts import get_object_or_404, render

from quanly.blockchain_utils import *
import traceback

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
from .user_utils import Wallet, VoteValidator, get_client_ip
from quanly.blockchain_core import Blockchain, VoteTransaction
from quanly.blockchain_utils import get_blockchain_file_path


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

    now = timezone.now()
    is_ended = now > ballot.end_date



    # my_vote = Vote.objects.prefetch_related('candidates').get(
    #     ballot=ballot, 
    #     voter_public_key=request.user.voter.public_key
    # )
    my_vote = Vote.objects.get(
    ballot=ballot, 
    voter_public_key=request.user.voter.public_key
)



    context = {
        'baucu': ballot,
        'my_vote': my_vote,
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
    if request.method != 'POST':
        return redirect('chitiet_baucu_u', id=id)

    ballot = get_object_or_404(Ballot, pk=id)
    blockchain_export_dir = os.path.join(settings.BASE_DIR, 'quanly', 'save_blockchain')
    file_path = get_blockchain_file_path(ballot.id, blockchain_export_dir)
    
    is_valid, verify_msg = verify_blockchain_integrity(ballot.id, blockchain_export_dir)
    if not is_valid:
        tampered_backup_path = backup_tampered_file(ballot.id, blockchain_export_dir)
        log_tampering_event(
            ballot=ballot, verify_msg=verify_msg, user=request.user,
            ip_address=get_client_ip(request), backup_path=tampered_backup_path
        )
        if not restore_from_backup(ballot.id, blockchain_export_dir):
            messages.error(request, "LỖI BẢO MẬT: Sổ cái đã bị thay đổi và không có bản sao lưu để phục hồi.")
            return redirect('chitiet_baucu_u', id=id)
        messages.warning(request, "CẢNH BÁO: Sổ cái đã bị thay đổi! Hệ thống đã tự động phục hồi. Giao dịch của bạn sẽ được xử lý.")

    try:
        # --- GIAI ĐOẠN 1: ĐỌC VÀ XÁC MINH SỔ CÁI HIỆN TẠI ---
        blockchain = Blockchain(difficulty=2)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                chain_data = json.load(f).get("blocks", [])
                blockchain = Blockchain.from_dict_list(chain_data, difficulty=2)
            
            is_valid, error_msg = blockchain.is_chain_valid()
            if not is_valid:
                messages.error(request, f"LỖI BẢO MẬT: Sổ cái đã bị thay đổi! {error_msg}")
                return redirect('chitiet_baucu_u', id=id)

        # --- GIAI ĐOẠN 2: XÁC THỰC QUYỀN VÀ DỮ LIỆU CỦA NGƯỜI DÙNG ---
        if not hasattr(request.user, 'voter'):
            raise ValueError('Bạn cần đăng ký làm cử tri để bỏ phiếu.')
        voter = request.user.voter
        
        for block in blockchain.chain:
            for tx in block.transactions:
                if tx.voter_public_key == voter.public_key:
                    raise ValueError('Bạn đã bỏ phiếu trong cuộc bầu cử này rồi.')

        candidate_ids = request.POST.getlist('candidates')
        key_data = json.loads(request.FILES['key_file'].read().decode('utf-8'))
        wallet = Wallet(private_key_pem_b64=key_data.get('private_key_pem_b64'), public_key_str=key_data.get('public_key'))
        if wallet.public_key_str != voter.public_key:
            raise ValueError('File khóa không khớp với tài khoản của bạn.')
        
        timestamp_str = timezone.localtime(timezone.now()).isoformat()
        sorted_ids_str = ",".join(sorted(candidate_ids))
        data_to_sign = f"{ballot.id}-{sorted_ids_str}-{voter.public_key}-{timestamp_str}"
        signature = wallet.sign(data_to_sign)
        if not Wallet.verify(voter.public_key, data_to_sign, signature):
            raise ValueError('Lỗi xác minh chữ ký.')

        # --- GIAI ĐOẠN 3: CẬP NHẬT VÀ GHI LẠI BLOCKCHAIN ---
        with transaction.atomic():
            vote_record = Vote.objects.create(
                ballot=ballot, voter_public_key=voter.public_key,
                signature=signature, timestamp=timestamp_str
            )
            vote_record.candidates.set(candidate_ids)

        candidate_names = ", ".join(Candidate.objects.filter(id__in=candidate_ids).values_list('name', flat=True))
        new_transaction = VoteTransaction(
            vote_id=vote_record.id,
            candidate_names=candidate_names,
            voter_public_key=voter.public_key,
            signature=signature,
            timestamp=timezone.localtime(timezone.now()).isoformat()
        )
        
        blockchain.add_block([new_transaction])
        
        full_data = {
            "ballot_id": ballot.id,
            "ballot_title": ballot.title,
            "exported_at": timezone.localtime(timezone.now()).isoformat(),
            "blocks": blockchain.to_dict_list()
        }


        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, indent=4)

        
        # --- THÊM BƯỚC TẠO BACKUP ---
        # Tạo backup của file cũ TRƯỚC KHI ghi đè
        create_backup(ballot.id, blockchain_export_dir)
        # --- KẾT THÚC BƯỚC TẠO BACKUP ---

        messages.success(request, 'Bỏ phiếu thành công!')
        return redirect('chitiet_baucu_u', id=id)

    except Exception as e:
        traceback.print_exc()
        messages.error(request, f'Đã có lỗi xảy ra: {e}')
        return redirect('chitiet_baucu_u', id=id)