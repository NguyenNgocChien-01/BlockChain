import os
import json
from collections import Counter
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.core.management import call_command
from django.conf import settings

from quanly.crypto_utils import generate_threshold_keys
from .models import Ballot, Candidate, Vote, Voter, User, UserTamperLog
from quanly.blockchain_core import Blockchain, VoteTransaction
from quanly.blockchain_utils import get_blockchain_file_path # Chỉ dùng hàm này
from collections import Counter
import re
from django.db import transaction
# Create your views here.
from django.core.mail import send_mail

BLOCKCHAIN_EXPORT_DIR = os.path.join(settings.BASE_DIR, 'quanly', 'save_blockchain')
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
    if request.method == "POST":
        tieude = request.POST.get('tieude')
        mota = request.POST.get('mota')
        tgbd = request.POST.get('start_date')
        tgkt = request.POST.get('end_date')
        max_choices = request.POST.get('max_choices', 1)
        ballot_type = request.POST.get('type', 'PUBLIC')
        
        use_security_settings = 'toggleSecuritySettings' in request.POST

        try:
            # --- BƯỚC 1: Xử lý trước khi tạo Ballot ---
            if use_security_settings:
                council_members_ids = request.POST.getlist('council_members')
                threshold_value = request.POST.get('threshold')

                if not threshold_value or int(threshold_value) > len(council_members_ids):
                    raise ValueError('Ngưỡng giải mã không hợp lệ hoặc lớn hơn số lượng thành viên hội đồng.')
                
                pk_json, sk_shares_json = generate_threshold_keys(
                    num_members=len(council_members_ids), 
                    threshold=int(threshold_value)
                )
                
                council_members_qs = User.objects.filter(id__in=council_members_ids)
                
                # Sẽ gửi email và phân phối khóa ở cuối
            else:
                pk_json = None
                sk_shares_json = None
                council_members_qs = User.objects.none() # Empty queryset

            # --- BƯỚC 2: Tạo Ballot trong transaction.atomic() ---
            with transaction.atomic():
                new_ballot = Ballot.objects.create(
                    title=tieude,
                    description=mota,
                    start_date=tgbd,
                    end_date=tgkt,
                    type=ballot_type,
                    max_choices=max_choices,
                    # Lưu khóa công khai và ngưỡng vào Ballot model
                    council_public_key=pk_json,
                    threshold=int(threshold_value) if use_security_settings else 0
                )
                
                # Gán các thành viên vào mối quan hệ ManyToMany
                if use_security_settings:
                    new_ballot.council_members.set(council_members_qs)

                if ballot_type == 'PRIVATE':
                    voter_ids = request.POST.getlist('eligible_voters')
                    if voter_ids:
                        new_ballot.eligible_voters.set(voter_ids)

            # --- BƯỚC 3: GỬI EMAIL SAU KHI TRANSACTION ĐÃ THÀNH CÔNG ---
            if use_security_settings:
                for member, key_share in zip(council_members_qs, sk_shares_json):
                    subject = f"Mảnh khóa Giải mã cho cuộc bầu cử '{new_ballot.title}'"
                    message = f"""
Xin chào {member.username},

Bạn đã được chỉ định làm thành viên của Hội đồng Kiểm phiếu cho cuộc bầu cử: '{new_ballot.title}'.
Mảnh khóa bí mật của bạn là: {key_share}

Bạn sẽ cần mảnh khóa này để tham gia giải mã phiếu bầu khi cuộc bầu cử kết thúc. Vui lòng lưu trữ nó ở nơi an toàn và tuyệt đối không chia sẻ với bất kỳ ai khác.

Trân trọng,
Hệ thống Bầu cử
"""
                    if member.email:
                        try:
                            send_mail(subject, message, settings.EMAIL_HOST_USER, [member.email], fail_silently=False)
                            print(f"Đã gửi mảnh khóa đến {member.email}")
                        except Exception as e:
                            print(f"Lỗi khi gửi email đến {member.email}: {e}")
                            messages.warning(request, f"Lỗi gửi email đến thành viên '{member.username}'. Vui lòng liên hệ và phân phối thủ công.")

            messages.success(request, 'Thêm cuộc bầu cử thành công!')
        except ValueError as e:
            messages.error(request, f'Lỗi xác thực: {e}')
        except Exception as e:
            messages.error(request, f'Lỗi khi thêm cuộc bầu cử: {e}')
            
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
    """Hiển thị kết quả bằng cách đọc file JSON, chỉ sau khi cuộc bầu cử kết thúc."""
    baucu = get_object_or_404(Ballot, id=id)
    if baucu.end_date > timezone.now():
        messages.warning(request, "Kết quả chỉ có thể xem sau khi cuộc bầu cử kết thúc.")
        return redirect('chitiet_baucu', id=id)

    filepath = get_blockchain_file_path(ballot_id=id, base_export_dir=BLOCKCHAIN_EXPORT_DIR)
    ketqua_tu_file = []
    tong_so_phieu = 0

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        vote_counts = Counter()
        for block in data.get("blocks", []):
            data_string = block.get("data", "")
            if "Genesis" in data_string or "No transactions" in data_string: continue
            
            for summary in data_string.split(';'):
                try:
                    name_part = summary.split(':')[1].strip()
                    candidate_names = [name.strip() for name in name_part.split(',')]
                    for name in candidate_names:
                        if name: vote_counts[name] += 1
                except IndexError: continue
        
        sorted_results = vote_counts.most_common()
        tong_so_phieu = sum(vote_counts.values())
        for name, count in sorted_results:
            ketqua_tu_file.append({
                'candidate__name': name,
                'so_phieu': count,
                'phan_tram': round((count / tong_so_phieu) * 100, 2) if tong_so_phieu > 0 else 0
            })

    except FileNotFoundError:
        messages.error(request, "Chưa có sổ cái blockchain cho cuộc bầu cử này. Cần phải có ít nhất một phiếu bầu.")
    except Exception as e:
        messages.error(request, f"Lỗi khi đọc sổ cái: {e}")
        
    context = {
        'baucu': baucu,
        'ketqua': ketqua_tu_file,
        'tong_so_phieu': tong_so_phieu,
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

