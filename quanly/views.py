import os
import json
from collections import Counter
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.core.management import call_command
from django.conf import settings
from django.core.mail import EmailMessage
from quanly.crypto_utils import generate_threshold_keys, combine_shares_and_decrypt
from .models import *
from quanly.blockchain_core import Blockchain, VoteTransaction
from quanly.blockchain_utils import *
from collections import Counter
import re
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.db import transaction
# Create your views here.
from django.core.mail import send_mail

BLOCKCHAIN_EXPORT_DIR = os.path.join(settings.BASE_DIR, 'quanly', 'save_blockchain')
BLOCKCHAIN_EXPORT_DIR_RESULT =  os.path.join(settings.BASE_DIR, 'quanly', 'save_blockchain_result')


def admin_login_view(request):
    """
    View xử lý việc đăng nhập cho tài khoản quản trị (admin).
    """
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('trangchu') # Nếu đã đăng nhập, chuyển đến trang chủ admin

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # --- KIỂM TRA QUAN TRỌNG: Chỉ cho phép staff user đăng nhập ---
            if user.is_staff:
                auth_login(request, user)
                return redirect('trangchu')
            else:
                messages.error(request, 'Tài khoản này không có quyền truy cập vào khu vực quản trị.')
        else:
            messages.error(request, 'Tên đăng nhập hoặc mật khẩu không đúng.')
    
    return render(request, 'adminpages/login.html')


def admin_logout_view(request):
    """View xử lý việc đăng xuất cho admin."""
    auth_logout(request)
    messages.info(request, 'Bạn đã đăng xuất khỏi khu vực quản trị.')
    return redirect('admin_login')

def trangchu(request):
    return render(request,'adminpages/index.html')
def chart(request):
    return render(request,'adminpages/chart.html')

def baucu(request):

    keyword = request.GET.get('keyword', '')
    status_filter = request.GET.get('status_filter', 'all')
    type_filter = request.GET.get('type_filter', 'all')
    
    now = timezone.now()
    all_ballots = Ballot.objects.all()

    total_ballots = all_ballots.count()
    ongoing_ballots = all_ballots.filter(start_date__lte=now, end_date__gte=now).count()
    upcoming_ballots = all_ballots.filter(start_date__gt=now).count()
    ended_ballots = all_ballots.filter(end_date__lt=now).count()

   
    if status_filter == 'ongoing':
        all_ballots = all_ballots.filter(start_date__lte=now, end_date__gte=now)
    elif status_filter == 'upcoming':
        all_ballots = all_ballots.filter(start_date__gt=now)
    elif status_filter == 'ended':
        all_ballots = all_ballots.filter(end_date__lt=now)

    if type_filter == 'public':
        all_ballots = all_ballots.filter(type='PUBLIC')
    elif type_filter == 'private':
        all_ballots = all_ballots.filter(type='PRIVATE')

    if keyword:
        all_ballots = all_ballots.filter(
            Q(title__icontains=keyword) | Q(description__icontains=keyword)
        )
    
    all_ballots = all_ballots.order_by('-start_date')
    
    voters = Voter.objects.select_related('user').all()
    potential_council_members = User.objects.filter(is_staff=True)
            
    context = {
        'baucus': all_ballots,
        'keyword': keyword,
        'now': now,
        'voters': voters,
        'status_filter': status_filter, 
        'type_filter': type_filter,
        'total_ballots': total_ballots,
        'ongoing_ballots': ongoing_ballots,
        'upcoming_ballots': upcoming_ballots,
        'ended_ballots': ended_ballots,
        'potential_council_members': potential_council_members,
    }
    
    return render(request, 'adminpages/baucu/baucu.html', context)

from django.utils.dateparse import parse_datetime
def add_baucu(request):
    """
    Xử lý việc thêm một cuộc bầu cử mới.
    Mật mã Ngưỡng được áp dụng bắt buộc cho mọi trường hợp.
    Các mảnh khóa được gửi trực tiếp qua email, không lưu vào CSDL.
    """
    if request.method != "POST":
        return redirect('baucu')

    try:
        # --- 1. LẤY VÀ XÁC THỰC DỮ LIỆU TỪ FORM ---
        member_ids = request.POST.getlist('council_members')
        threshold = int(request.POST.get('threshold'))
        num_members = len(member_ids)

        if threshold > num_members or threshold < 2:
            raise ValueError("Ngưỡng giải mã phải lớn hơn 1 và không được lớn hơn tổng số thành viên.")

        # --- 2. TẠO KHÓA CÔNG KHAI VÀ CÁC MẢNH KHÓA BÍ MẬT ---
        public_key_pem, secret_key_shares = generate_threshold_keys(num_members, threshold)

        # --- 3. TẠO VÀ LƯU DỮ LIỆU VÀO CSDL TRONG MỘT TRANSACTION ---
        with transaction.atomic():
            new_ballot = Ballot.objects.create(
                title=request.POST.get('tieude'),
                description=request.POST.get('mota'),
                start_date=request.POST.get('start_date'),
                end_date=request.POST.get('end_date'),
                type=request.POST.get('type', 'PUBLIC'),
                max_choices=request.POST.get('max_choices', 1),
                council_public_key=public_key_pem,
                threshold=threshold
            )
            
            if new_ballot.type == 'PRIVATE':
                voter_ids = request.POST.getlist('eligible_voters')
                new_ballot.eligible_voters.set(voter_ids)
            
            council_users = User.objects.filter(pk__in=member_ids)
            new_ballot.council_members.set(council_users)
        
        # --- 4. GỬI EMAIL SAU KHI TRANSACTION ĐÃ THÀNH CÔNG ---
        # Lấy lại danh sách user từ CSDL để đảm bảo tính nhất quán
        council_users_to_email = new_ballot.council_members.all()
        for i, member in enumerate(council_users_to_email):
            try:
                # Lấy mảnh khóa tương ứng từ danh sách đã tạo
                key_share = secret_key_shares[i]
                
                subject = f"Mảnh khóa Bí mật cho Cuộc bầu cử: {new_ballot.title}"
                message_body = (
                    f"Xin chào {member.get_full_name() or member.username},\n\n"
                    f"Bạn đã được chỉ định làm thành viên Hội đồng Kiểm phiếu cho cuộc bầu cử '{new_ballot.title}'.\n\n"
                    f"Trong file đính kèm là mảnh khóa bí mật của bạn. Vui lòng tải về và lưu trữ nó một cách cẩn thận và an toàn tuyệt đối.\n\n"
                    f"Trân trọng,\nHệ thống Bầu cử."
                )
                
                sender_email = getattr(settings, 'EMAIL_HOST_USER', 'noreply@example.com')
                if member.email:
                    email = EmailMessage(subject, message_body, sender_email, [member.email])
                    attachment_filename = f"key_share_{new_ballot.id}_{member.username}.key"
                    email.attach(attachment_filename, key_share, 'text/plain')
                    email.send(fail_silently=False)
            except Exception as mail_error:
                messages.warning(request, f"Lỗi gửi email đến thành viên '{member.username}'. Vui lòng phân phối thủ công.")

        messages.success(request, f"Đã tạo thành công cuộc bầu cử và gửi mảnh khóa đến Hội đồng.")

    except ValueError as ve:
        messages.error(request, f"Lỗi xác thực dữ liệu: {ve}")
    except Exception as e:
        messages.error(request, f"Đã có lỗi không xác định xảy ra khi tạo bầu cử: {e}")

    return redirect('baucu')

def delete_baucu(request, id):

    baucu = get_object_or_404(Ballot, id=id)

    num_votes = Vote.objects.filter(ballot=baucu).count()

    if num_votes > 0:

        messages.error(request, f"Không thể xóa cuộc bầu cử '{baucu.title}' vì đã có {num_votes} phiếu bầu được ghi nhận.")
        return redirect('baucu')
    
    try:
        baucu.delete()
        messages.success(request, f"Đã xóa cuộc bầu cử '{baucu.title}' thành công.")
    except Exception as e:
        messages.error(request, f"Lỗi khi xóa cuộc bầu cử: {e}")
    
    return redirect('baucu')

def edit_baucu(request, id):

    baucu_obj = get_object_or_404(Ballot, id=id)
    if request.method == "POST":
        baucu_obj.title = request.POST.get('tieude')
        baucu_obj.description = request.POST.get('mota')
        baucu_obj.start_date = request.POST.get('start_date')
        baucu_obj.end_date = request.POST.get('end_date')
        baucu_obj.max_choices = request.POST.get('max_choices',1) 
        
        ballot_type = request.POST.get('type', 'PUBLIC')
        baucu_obj.type = ballot_type
        
        baucu_obj.save() 


        if ballot_type == 'PRIVATE':
            voter_ids = request.POST.getlist('eligible_voters')
            baucu_obj.eligible_voters.set(voter_ids)
        else:

            baucu_obj.eligible_voters.clear()

    return redirect('baucu')

def chitiet_baucu(request, id):
    baucu = get_object_or_404(Ballot, id=id)
    ungcuviens = Candidate.objects.filter(ballot=baucu)
    # ungcuviens_khac = Candidate.objects.exclude(ballot=baucu)
    now = timezone.now()
    is_active = baucu.start_date <= now and baucu.end_date >= now


    eligible_voters_list = None
    if baucu.type == 'PRIVATE':
        eligible_voters_list = baucu.eligible_voters.select_related('user').all()

    potential_council_members = User.objects.filter(is_staff=True)
    context = {
        'baucu': baucu,
        'ungcuviens': ungcuviens,
        'is_active': is_active,
        'eligible_voters_list': eligible_voters_list,
        'potential_council_members': potential_council_members,
        # 'ungcuviens_khac':ungcuviens_khac
    }
    return render(request, 'adminpages/baucu/chitiet.html', context)

def add_ungcuvien(request, id):
    baucu = get_object_or_404(Ballot,id = id)
    if request.method == "POST":
        ten = request.POST.get('name')
        mota = request.POST.get('description')
        hinh = request.FILES.get('image')

        Candidate.objects.create(
            name=ten,
            description=mota,
            avatar=hinh,
            ballot = baucu
        )
    return redirect('chitiet_baucu', id=id)

def delete_ungcuvien(request, id):
    ungcuvien = get_object_or_404(Candidate, id=id)
    
    baucu_id = ungcuvien.ballot.id

    # if ungcuvien.avatar:
    #     if os.path.isfile(ungcuvien.avatar.path):
    #         os.remove(ungcuvien.avatar.path)
            
    # ungcuvien.delete()
    
    return redirect('chitiet_baucu', id=baucu_id)

def ketthuc_baucu(request, id):
    ballot = get_object_or_404(Ballot, id=id)

    # Check if the ballot has already ended
    now = timezone.now()
    if ballot.end_date < now:
        messages.warning(request, f"Cuộc bầu cử '{ballot.title}' đã kết thúc rồi.")
        return redirect('chitiet_baucu', id=id)

    try:
        ballot.end_date = now
        ballot.save()
        messages.success(request, f"Đã kết thúc cuộc bầu cử '{ballot.title}' ngay lập tức.")
    except Exception as e:
        messages.error(request, f"Lỗi khi kết thúc cuộc bầu cử: {e}")
    
    return redirect('chitiet_baucu', id=id)

def edit_ungcuvien(request, id):
    ungcuvien = get_object_or_404(Candidate, id=id)

    if request.method == "POST":
        ungcuvien.name = request.POST.get('name')
        ungcuvien.description = request.POST.get('description')
        
        if request.FILES.get('image'):
            ungcuvien.avatar = request.FILES.get('image')

    ungcuvien.save()
    baucu_id = ungcuvien.ballot.id

    return redirect('chitiet_baucu', id=baucu_id)


    # Phần cua user
def ds_user(request):
    keyword = request.GET.get('keyword', '')
    
    # Bắt đầu với một QuerySet chứa tất cả user.
    # Dùng select_related('voter') để tối ưu, lấy thông tin Voter cùng lúc,
    # tránh việc truy vấn lặp lại vào database.
    users_list = User.objects.select_related('voter').all().order_by('id')

    # Nếu có keyword, áp dụng bộ lọc để thu hẹp kết quả
    if keyword:
        users_list = users_list.filter(
            Q(username__icontains=keyword) |
            Q(first_name__icontains=keyword) |
            Q(last_name__icontains=keyword) |
            Q(email__icontains=keyword)
        )
        
    context = {
        'users': users_list,
        'keyword': keyword,
    }
    
    return render(request, 'adminpages/user/user.html', context)


def add_user(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('firstname', '').strip()
        last_name = request.POST.get('lastname', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        # Kiểm tra các trường không được để trống
        if not all([username, first_name, last_name, email, password, password2]):
            messages.error(request, 'Vui lòng điền vào các trường còn trống.')
            return redirect('add_user')

        # Kiểm tra tên đăng nhập chỉ chứa chữ và số
        if not re.match(r'^[A-Za-z0-9]+$', username):
            messages.error(request, 'Tên đăng nhập chỉ chứa ký tự chữ và số.')
            return redirect('add_user')

        # Kiểm tra độ dài mật khẩu
        if len(password) <= 10:
            messages.error(request, 'Mật khẩu phải có độ dài hơn 10 ký tự.')
            return redirect('add_user')

        # Kiểm tra xác nhận mật khẩu
        if password != password2:
            messages.error(request, 'Mật khẩu xác nhận không khớp.')
            return redirect('add_user')

        # Kiểm tra username đã tồn tại chưa
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Tên đăng nhập này đã tồn tại!')
            return redirect('add_user')

        # Tạo người dùng mới
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name
        )

        messages.success(request, f'Tạo người dùng "{username}" thành công!')
        return redirect('ds_user')  # Chuyển hướng về danh sách người dùng

    return redirect('ds_user')


def delete_user(request, id):
    user = get_object_or_404(User, id=id)
    user.delete()
    return redirect('ds_user')

def edit_user(request, id):
    user = get_object_or_404(User, id=id)

    if request.method == "POST":
        user.username = request.POST.get('username')
        user.first_name = request.POST.get('firstname')
        user.last_name = request.POST.get('lastname')
        user.email = request.POST.get('email')

    user.save()

    return redirect('ds_user')

def revoke_voter_status(request, user_id):

    user_to_update = get_object_or_404(User, pk=user_id)
    
    if hasattr(user_to_update, 'voter'):
        try:
            # Việc xóa Voter sẽ xóa cả khóa của họ
            user_to_update.voter.delete()
            messages.success(request, f'Đã hủy bỏ vai trò cử tri của người dùng "{user_to_update.username}".')
        except Exception as e:
            messages.error(request, f'Đã có lỗi xảy ra: {e}')
    else:
        messages.warning(request, f'Người dùng "{user_to_update.username}" không phải là cử tri.')
        
    return redirect('ds_user')

def ketqua_baucu(request, id):
    """
    Hiển thị kết quả bầu cử bằng cách đọc file JSON đã được giải mã,
    chỉ sau khi "Lễ Kiểm phiếu" đã hoàn tất.
    """
    baucu = get_object_or_404(Ballot, id=id)



    # 2. Lấy đường dẫn đến file kết quả đã giải mã
    # Sử dụng đường dẫn mới đã được định nghĩa
    original_path = get_blockchain_file_path(ballot_id=id, base_export_dir=BLOCKCHAIN_EXPORT_DIR_RESULT)
    base, ext = os.path.splitext(os.path.basename(original_path))
    decrypted_filename = f"{base}_decrypted_results.json"
    filepath = os.path.join(BLOCKCHAIN_EXPORT_DIR_RESULT, decrypted_filename)

    try:
        # 3. Đọc và hiển thị kết quả từ file
        with open(filepath, 'r', encoding='utf-8') as f:
            results_data = json.load(f)
        
        ketqua = results_data.get('results', [])
        tong_so_phieu = sum(item['count'] for item in ketqua)

    except FileNotFoundError:
        messages.error(request, "Không tìm thấy file kết quả đã giải mã.")
        return redirect('chitiet_baucu', id=id)
    except Exception as e:
        messages.error(request, f"Lỗi khi đọc file kết quả: {e}")
        return redirect('chitiet_baucu', id=id)
        
    context = {
        'ballot': baucu,
        'results': ketqua, # Giữ tên biến 'ketqua' để khớp với template

    }

    return render(request, 'adminpages/baucu/ketqua.html', context)

def danhsach_phieubau(request, ballot_id):
    """Hiển thị danh sách chi tiết các phiếu bầu từ CSDL."""
    ballot = get_object_or_404(Ballot, id=ballot_id)
    votes = Vote.objects.filter(ballot=ballot).prefetch_related('candidates').order_by('timestamp')
    vote_details = []
    for vote in votes:
        voter_username = Voter.objects.filter(public_key=vote.voter_public_key).first().user.username or "Không xác định"
        vote_details.append({
            'id': vote.id,
            'candidate_names': ", ".join([c.name for c in vote.candidates.all()]), # Sửa lỗi
            'voter_username': voter_username,
            'signature': vote.signature,
            'timestamp': vote.timestamp,
            'block_id': vote.block.id if vote.block else 'Chưa vào khối'
        })
    context = {'ballot': ballot, 'vote_details': vote_details}
    return render(request, 'adminpages/baucu/danhsach_phieubau.html', context)


def lichsu_change(request):
    """Hiển thị lịch sử các cảnh báo an ninh."""
    context = {'logs': UserTamperLog.objects.all().order_by('-timestamp')}
    return render(request, 'adminpages/tamperlog.html', context)

# def tally_ceremony_view(request, ballot_id):
#     """
#     View xử lý toàn bộ quy trình kiểm phiếu:
#     1. Thu thập các mảnh khóa từ thành viên Hội đồng.
#     2. Lưu trữ các mảnh khóa an toàn vào CSDL.
#     3. Khi đủ ngưỡng, thực hiện giải mã, kiểm phiếu và công khai hóa kết quả.
#     """
#     ballot = get_object_or_404(Ballot, pk=ballot_id)
    
#     # --- KIỂM TRA ĐIỀU KIỆN TIÊN QUYẾT ---
#     if ballot.end_date > timezone.now():
#         messages.error(request, "Không thể kiểm phiếu khi cuộc bầu cử vẫn đang diễn ra.")
#         return redirect('chitiet_baucu', id=ballot_id)

#     # Lấy các mảnh khóa đã nộp từ CSDL
#     submitted_shares_qs = SubmittedKeyShare.objects.filter(ballot=ballot)
#     submitted_member_ids = set(submitted_shares_qs.values_list('council_member_id', flat=True))

#     # --- XỬ LÝ CÁC HÀNH ĐỘNG POST ---
#     if request.method == 'POST':
#         # Xử lý khi một thành viên hội đồng nộp mảnh khóa
#         if 'submit_share' in request.POST:
#             return handle_submit_share(request, ballot)
        
#         # Xử lý khi bấm nút "Giải mã và Kiểm phiếu"
#         elif 'tally_votes' in request.POST:
#             return handle_tally_votes(request, ballot, submitted_shares_qs)

#     # --- HIỂN THỊ TRANG (GET REQUEST) ---
#     # Lấy danh sách thành viên hội đồng và trạng thái nộp khóa của họ
#     council_members = ballot.council_members.all()
#     members_status = []
#     for member in council_members:
#         members_status.append({
#             'user': member,
#             'has_submitted': member.id in submitted_member_ids
#         })

#     context = {
#         'ballot': ballot,
#         'members_status': members_status,
#         'submitted_count': len(submitted_member_ids),
#         'threshold': ballot.threshold,
#         'can_tally': len(submitted_member_ids) >= ballot.threshold
#     }
#     return render(request, 'adminpages/baucu/tally_ceremony.html', context)



# def handle_submit_share(request, ballot):
#     """Hàm phụ: Xử lý logic khi một thành viên nộp mảnh khóa."""
#     if not ballot.council_members.filter(pk=request.user.pk).exists():
#         messages.error(request, "Bạn không phải là thành viên của Hội đồng Kiểm phiếu này.")
#         return redirect('tally_ceremony', ballot_id=ballot.id)

#     key_share_file = request.FILES.get('key_share_file')
#     if key_share_file:
#         try:
#             key_share = key_share_file.read().decode('utf-8').strip()
#             # Lưu mảnh khóa vào CSDL, tự động cập nhật nếu đã tồn tại
#             SubmittedKeyShare.objects.update_or_create(
#                 ballot=ballot,
#                 council_member=request.user,
#                 defaults={'key_share': key_share}
#             )
#             messages.success(request, "Đã nhận thành công mảnh khóa của bạn.")
#         except Exception as e:
#             messages.error(request, f"Lỗi khi đọc file mảnh khóa: {e}")
#     else:
#         messages.error(request, "Vui lòng tải lên file mảnh khóa.")
    
#     return redirect('tally_ceremony', ballot_id=ballot.id)



# def handle_tally_votes(request, ballot, submitted_shares_qs):
#     """Hàm phụ: Xử lý logic giải mã và kiểm phiếu."""
#     key_shares_from_db = list(submitted_shares_qs.values_list('key_share', flat=True))
#     unique_key_shares_list = list(set(key_shares_from_db))

#     if len(unique_key_shares_list) < ballot.threshold:
#         messages.error(request, f"Chưa đủ số lượng mảnh khóa HỢP LỆ để giải mã.")
#         return redirect('tally_ceremony', ballot_id=ballot.id)

#     try:
#         all_votes = Vote.objects.filter(ballot=ballot)
#         vote_counts = Counter()
#         decrypted_votes_map = {} # Lưu lại kết quả giải mã để dùng sau

#         # --- GIAI ĐOẠN 1: GIẢI MÃ VÀ KIỂM ĐẾM ---
#         for vote in all_votes:
#             decrypted_ids = combine_shares_and_decrypt(unique_key_shares_list, vote.encrypted_vote_data)
#             decrypted_votes_map[vote.id] = decrypted_ids
#             for candidate_id in decrypted_ids:
#                 vote_counts[candidate_id] += 1
        
#         # --- GIAI ĐOẠN 2: HOÀN TẤT VÀ CÔNG KHAI HÓA (CẬP NHẬT CSDL) ---
#         with transaction.atomic():
#             # Cập nhật CSDL với kết quả đã giải mã
#             for vote_id, candidate_ids in decrypted_votes_map.items():
#                 vote_obj = Vote.objects.get(pk=vote_id)
#                 # Giả định model Vote có trường ManyToManyField tên là 'candidates'
#                 if hasattr(vote_obj, 'candidates'):
#                     vote_obj.candidates.set(candidate_ids)

#         # (Tùy chọn) Tạo file JSON cuối cùng đã được giải mã
    

#         # --- GIAI ĐOẠN 3: HIỂN THỊ KẾT QUẢ ---
#         results = []
#         # Lấy danh sách ID của tất cả các ứng viên đã nhận được phiếu bầu
#         voted_candidate_ids = list(vote_counts.keys())
#         # Truy vấn CSDL một lần duy nhất để lấy tên của các ứng viên này
#         candidates_info = {c.id: c.name for c in Candidate.objects.filter(id__in=voted_candidate_ids)}

        
#         for candidate_id, count in vote_counts.items():
#             candidate_name = Candidate.objects.get(id=candidate_id).name
#             results.append({
#                 'name': candidates_info.get(candidate_id, f" {candidate_name }"),
#                 'count': count
#             })
        
#         sorted_results = sorted(results, key=lambda x: x['count'], reverse=True)
        
#         save_decrypted_blockchain_to_json(ballot, sorted_results, BLOCKCHAIN_EXPORT_DIR_RESULT )
#         # Xóa các mảnh khóa đã nộp sau khi hoàn tất để tăng bảo mật
#         # submitted_shares_qs.delete()

#         messages.success(request, "Kiểm phiếu và giải mã hoàn tất! Kết quả đã được công khai hóa.")
#         return render(request, 'adminpages/baucu/ketqua.html', {
#             'ballot': ballot,
#             'results': sorted_results
#         })

#     except Exception as e:
#         messages.error(request, f"Lỗi nghiêm trọng khi giải mã: {e}")
#         return redirect('tally_ceremony', ballot_id=ballot.id)


def tally_ceremony_view(request, ballot_id):
    """
    View chính xử lý toàn bộ quy trình "Lễ Kiểm phiếu".
    """
    ballot = get_object_or_404(Ballot, pk=ballot_id)
    
    # Điều kiện tiên quyết: Cuộc bầu cử phải kết thúc
    if ballot.end_date > timezone.now():
        messages.error(request, "Không thể kiểm phiếu khi cuộc bầu cử vẫn đang diễn ra.")
        return redirect('chitiet_baucu', id=ballot_id)

    submitted_shares_qs = SubmittedKeyShare.objects.filter(ballot=ballot)
    submitted_member_ids = set(submitted_shares_qs.values_list('council_member_id', flat=True))

    # Xử lý các hành động POST
    if request.method == 'POST':
        if 'submit_share' in request.POST:
            return handle_submit_share(request, ballot)
        elif 'tally_votes' in request.POST:
            return handle_tally_votes(request, ballot, submitted_shares_qs)

    # Hiển thị trang (GET request)
    council_members = ballot.council_members.all()
    members_status = []
    for member in council_members:
        members_status.append({
            'user': member,
            'has_submitted': member.id in submitted_member_ids
        })

    context = {
        'ballot': ballot,
        'members_status': members_status,
        'submitted_count': len(submitted_member_ids),
        'threshold': ballot.threshold,
        'can_tally': len(submitted_member_ids) >= ballot.threshold
    }
    return render(request, 'adminpages/baucu/tally_ceremony.html', context)


def handle_submit_share(request, ballot):
    """Hàm phụ: Xử lý logic khi một thành viên nộp mảnh khóa."""
    if not ballot.council_members.filter(pk=request.user.pk).exists():
        messages.error(request, "Bạn không phải là thành viên của Hội đồng Kiểm phiếu này.")
        return redirect('tally_ceremony', ballot_id=ballot.id)

    key_share_file = request.FILES.get('key_share_file')
    if key_share_file:
        try:
            key_share = key_share_file.read().decode('utf-8').strip()
            SubmittedKeyShare.objects.update_or_create(
                ballot=ballot,
                council_member=request.user,
                defaults={'key_share': key_share}
            )
            messages.success(request, "Đã nhận thành công mảnh khóa của bạn.")
        except Exception as e:
            messages.error(request, f"Lỗi khi đọc file mảnh khóa: {e}")
    else:
        messages.error(request, "Vui lòng tải lên file mảnh khóa.")
    
    return redirect('tally_ceremony', ballot_id=ballot.id)


def handle_tally_votes(request, ballot, submitted_shares_qs):
    """Hàm phụ: Xử lý logic giải mã, kiểm phiếu, và công khai hóa kết quả."""
    key_shares_from_db = list(submitted_shares_qs.values_list('key_share', flat=True))
    unique_key_shares_list = list(set(key_shares_from_db))

    if len(unique_key_shares_list) < ballot.threshold:
        messages.error(request, f"Chưa đủ số lượng mảnh khóa HỢP LỆ để giải mã.")
        return redirect('tally_ceremony', ballot_id=ballot.id)

    try:
        all_votes = Vote.objects.filter(ballot=ballot)
        vote_counts = Counter()
        decrypted_votes_map = {}

        # --- GIAI ĐOẠN 1: GIẢI MÃ VÀ KIỂM ĐẾM ---
        for vote in all_votes:
            decrypted_ids = combine_shares_and_decrypt(unique_key_shares_list, vote.encrypted_vote_data)
            decrypted_votes_map[vote.id] = decrypted_ids
            for candidate_id in decrypted_ids:
                vote_counts[candidate_id] += 1
        
        # --- GIAI ĐOẠN 2: HOÀN TẤT VÀ CÔNG KHAI HÓA ---
        with transaction.atomic():
            for vote_id, candidate_ids in decrypted_votes_map.items():
                vote_obj = Vote.objects.get(pk=vote_id)
                if hasattr(vote_obj, 'candidates'):
                    vote_obj.candidates.set(candidate_ids)
            
            # Đánh dấu cuộc bầu cử đã được kiểm phiếu
            ballot.is_tallied = True
            ballot.save()

        # --- GIAI ĐOẠN 3: CHUẨN BỊ DỮ LIỆU ĐỂ HIỂN THỊ VÀ LƯU FILE ---
        results = []
        voted_candidate_ids = list(vote_counts.keys())
        candidates_info = {c.id: c.name for c in Candidate.objects.filter(id__in=voted_candidate_ids)}
        
        for candidate_id, count in vote_counts.items():
            results.append({
                'name': candidates_info.get(candidate_id, f"ID không xác định: {candidate_id}"),
                'count': count
            })
        
        sorted_results = sorted(results, key=lambda x: x['count'], reverse=True)
        
        # Lưu kết quả đã giải mã ra file JSON công khai
        save_decrypted_blockchain_to_json(ballot, sorted_results, BLOCKCHAIN_EXPORT_DIR_RESULT)
        create_backup_for_results(ballot.id, BLOCKCHAIN_EXPORT_DIR_RESULT)
        
        # Xóa các mảnh khóa đã nộp sau khi hoàn tất để tăng bảo mật
        # submitted_shares_qs.delete()

        messages.success(request, "Kiểm phiếu và giải mã hoàn tất! Kết quả đã được công khai hóa.")
        return render(request, 'adminpages/baucu/tally_results.html', {
            'ballot': ballot,
            'results': sorted_results
        })

    except Exception as e:
        messages.error(request, f"Lỗi nghiêm trọng khi giải mã: {e}")
        return redirect('tally_ceremony', ballot_id=ballot.id)
