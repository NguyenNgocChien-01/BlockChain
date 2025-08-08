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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCKCHAIN_EXPORT_DIR_RESULT = os.path.join(settings.BASE_DIR, 'quanly', 'save_blockchain_result')
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
    """
    Hiển thị trang chi tiết. Nếu cuộc bầu cử đã kết thúc,
    sẽ tự động kiểm tra và hiển thị kết quả nếu có.
    """
    ballot = get_object_or_404(Ballot, pk=id)
    candidates = Candidate.objects.filter(ballot=ballot)
    
    now = timezone.now()
    is_active = ballot.start_date <= now <= ballot.end_date
    is_ended = now > ballot.end_date
    is_voter = hasattr(request.user, 'voter')
    has_voted = False

    # Các biến mới để xử lý kết quả
    election_results = None
    is_pending_tally = False
    winners = [] # Biến để lưu người thắng cuộc

    if is_voter:
        has_voted = Vote.objects.filter(
            ballot=ballot, 
            voter_public_key=request.user.voter.public_key
        ).exists()

    # Chỉ xử lý kết quả khi cuộc bầu cử đã kết thúc
    if is_ended:
        # --- LOGIC MỚI: TỰ ĐỘNG KIỂM TRA SỰ TỒN TẠI CỦA FILE KẾT QUẢ ---
        # Xây dựng đường dẫn đến file kết quả
        original_path = get_blockchain_file_path(ballot_id=id, base_export_dir=BLOCKCHAIN_EXPORT_DIR_RESULT)
        base, ext = os.path.splitext(os.path.basename(original_path))
        decrypted_filename = f"{base}_decrypted_results.json"
        filepath = os.path.join(BLOCKCHAIN_EXPORT_DIR_RESULT, decrypted_filename)

        # Nếu file kết quả đã tồn tại, đọc nó
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    results_data = json.load(f)
                election_results = results_data.get('results', [])

                # --- LOGIC MỚI: XÁC ĐỊNH NGƯỜI THẮNG CUỘC ---
                if election_results:
                    # 1. Tìm ra số phiếu cao nhất
                    max_votes = max(item['count'] for item in election_results)
                    
                    # 2. Tìm tên của tất cả các ứng viên có số phiếu bằng số phiếu cao nhất
                    winner_names = [
                        item['name'].strip() for item in election_results if item['count'] == max_votes
                    ]
                    
                    # 3. Lấy các đối tượng Candidate đầy đủ từ CSDL để có thể hiển thị ảnh
                    winners = Candidate.objects.filter(ballot=ballot, name__in=winner_names)

            except Exception:
                # Nếu file tồn tại nhưng bị lỗi, coi như vẫn đang chờ
                is_pending_tally = True
        else:
            # Nếu file chưa tồn tại, nghĩa là đang chờ kiểm phiếu
            is_pending_tally = True

    context = {
        'baucu': ballot,
        'ungcuviens': candidates,
        'is_active': is_active,
        'has_voted': has_voted,
        'is_voter': is_voter,
        'is_ended': is_ended,   
        'election_results': election_results, # Truyền kết quả
        'is_pending_tally': is_pending_tally, # Truyền trạng thái chờ
        'winners': winners, # Truyền danh sách người thắng cuộc
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
    """
    Hiển thị trang cho người dùng xem lại phiếu đã bầu của mình.
    Nếu cuộc bầu cử đã kết thúc và được kiểm phiếu, nó sẽ hiển thị
    các lựa chọn đã được giải mã.
    """
    ballot = get_object_or_404(Ballot, pk=id)
    
    if not hasattr(request.user, 'voter'):
        messages.error(request, "Tài khoản của bạn chưa được đăng ký làm cử tri.")
        return redirect('chitiet_baucu_u', id=id)

    now = timezone.now()
    is_ended = now > ballot.end_date
    my_vote_obj = None
    my_decrypted_candidates = [] # Biến để lưu các lựa chọn đã giải mã

    try:
        # Bước 1: Lấy bản ghi phiếu bầu của người dùng từ CSDL
        # Dùng prefetch_related để tối ưu, sẵn sàng lấy danh sách ứng viên nếu có
        my_vote_obj = Vote.objects.prefetch_related('candidates').get(
            ballot=ballot, 
            voter_public_key=request.user.voter.public_key
        )
    except Vote.DoesNotExist:
        my_vote_obj = None

    # Bước 2: Nếu cuộc bầu cử đã kết thúc và đã được kiểm phiếu,
    # lấy ra các lựa chọn đã được giải mã.
    # (Hàm kiểm phiếu của admin đã cập nhật lại trường 'candidates' trong CSDL)
    if is_ended and my_vote_obj:
        my_decrypted_candidates = my_vote_obj.candidates.all()

    context = {
        'baucu': ballot,
        'my_vote': my_vote_obj,
        'is_ended': is_ended, 
        'my_decrypted_candidates': my_decrypted_candidates, # Truyền danh sách đã giải mã
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

from quanly.crypto_utils import encrypt_vote
def bo_phieu(request, id):
    if request.method != 'POST':
        return redirect('chitiet_baucu_u', id=id)

    ballot = get_object_or_404(Ballot, pk=id)
    blockchain_export_dir = os.path.join(settings.BASE_DIR, 'quanly', 'save_blockchain')
    file_path = get_blockchain_file_path(ballot.id, blockchain_export_dir)

        # --- BƯỚC 1: KIỂM TRA TÍNH TOÀN VẸN CỦA SỔ CÁI (NẾU CÓ) ---
    is_valid, verify_msg = verify_blockchain_integrity(ballot.id, blockchain_export_dir)

    if not is_valid:
        tampered_backup_path = backup_tampered_file(ballot.id, blockchain_export_dir)

        log_tampering_event(
            ballot=ballot,
            verify_msg=verify_msg,
            user=request.user,
            ip_address=get_client_ip(request),
            backup_path=tampered_backup_path
        )

        # Thử phục hồi từ bản sao lưu
        if restore_from_backup(ballot.id, blockchain_export_dir):
            messages.warning(
                request,
                "CẢNH BÁO: Sổ cái đã bị thay đổi! Hệ thống đã tự động phục hồi. Giao dịch của bạn sẽ được xử lý."
            )
        else:
            messages.error(
                request,
                "LỖI BẢO MẬT: Sổ cái đã bị thay đổi và không có bản sao lưu để phục hồi."
            )
            return redirect('chitiet_baucu_u', id=id)

    try:
        # --- GIAI ĐOẠN 2: XÁC THỰC QUYỀN VÀ DỮ LIỆU CỦA NGƯỜI DÙNG ---
        if not hasattr(request.user, 'voter'):
            raise ValueError('Bạn cần đăng ký làm cử tri để bỏ phiếu.')
        voter = request.user.voter
        
        validator = VoteValidator(ballot, voter)
        is_ok, error_msg = validator.is_eligible()
        if not is_ok:
            raise ValueError(error_msg)

        candidate_ids = request.POST.getlist('candidates')
            # --- BƯỚC THÊM ĐỂ DEBUG ---
        print("Dữ liệu nhận được từ form:", request.POST)
        print("Files nhận được:", request.FILES)
        
        candidate_ids = request.POST.getlist('candidates')
        print("ID ứng cử viên nhận được:", candidate_ids)
        if not candidate_ids:
            raise ValueError('Bạn chưa chọn ứng cử viên nào.')
        if len(candidate_ids) > ballot.max_choices:
            raise ValueError(f"Bạn chỉ được phép chọn tối đa {ballot.max_choices} ứng cử viên.")

        # --- GIAI ĐOẠN 3: MÃ HÓA PHIẾU BẦU VÀ KÝ SỐ ---
        if not ballot.council_public_key:
            raise ValueError("Cuộc bầu cử này chưa được thiết lập an ninh. Vui lòng liên hệ quản trị viên.")

        encrypted_vote = encrypt_vote(ballot.council_public_key, candidate_ids)
        
        key_data = json.loads(request.FILES['key_file'].read().decode('utf-8'))
        wallet = Wallet(private_key_pem_b64=key_data.get('private_key_pem_b64'), public_key_str=key_data.get('public_key'))
        if wallet.public_key_str != voter.public_key:
            raise ValueError('File khóa không khớp với tài khoản của bạn.')
        
        timestamp_str = timezone.localtime(timezone.now()).isoformat()
        data_to_sign = f"{ballot.id}-{encrypted_vote}-{voter.public_key}-{timestamp_str}"
        signature = wallet.sign(data_to_sign)
        
        if not Wallet.verify(voter.public_key, data_to_sign, signature):
            raise ValueError('Lỗi xác minh chữ ký.')

        # --- GIAI ĐOẠN 4: CẬP NHẬT VÀ GHI LẠI BLOCKCHAIN ---
        with transaction.atomic():
            vote_record = Vote.objects.create(
                ballot=ballot,
                encrypted_vote_data=encrypted_vote,
                voter_public_key=voter.public_key,
                signature=signature,
                timestamp=timestamp_str
            )
        
        new_transaction = VoteTransaction(
            vote_id=vote_record.id,
            encrypted_vote=encrypted_vote,
            voter_public_key=voter.public_key,
            signature=signature,
            timestamp=vote_record.timestamp.isoformat()
        )
        
        blockchain = Blockchain(difficulty=2)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                chain_data = json.load(f).get("blocks", [])
                blockchain = Blockchain.from_dict_list(chain_data, difficulty=2)
        
        blockchain.add_block([new_transaction])
        
        blocks_data_list = blockchain.to_dict_list()
        full_blocks_json_string = json.dumps(blocks_data_list, indent=4, ensure_ascii=False, sort_keys=True)
        new_chain_hash = hashlib.sha256(full_blocks_json_string.encode('utf-8')).hexdigest()

        full_data = {
            "ballot_id": ballot.id,
            "ballot_title": ballot.title,
            "exported_at": timezone.localtime(timezone.now()).isoformat(),
            "chain_hash": new_chain_hash,
            "blocks": blocks_data_list
        }
        

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, indent=4, ensure_ascii=False)
        create_backup(ballot.id, blockchain_export_dir)

        messages.success(request, 'Bỏ phiếu thành công! Phiếu của bạn đã được mã hóa và ghi vào sổ cái.')
        return redirect('chitiet_baucu_u', id=id)

    except Exception as e:
        traceback.print_exc()
        messages.error(request, f'Đã có lỗi xảy ra: {e}')
        return redirect('chitiet_baucu_u', id=id)
