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
        try:
            # --- SINH KHÓA ---
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_key = private_key.public_key()
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )

            # --- TÁCH NỘI DUNG KHỎI HEADER/FOOTER ---
            def strip_pem_headers(pem_str):
                lines = pem_str.strip().splitlines()
                lines = [line for line in lines if not line.startswith("-----")]
                return ''.join(lines)

            public_base64 = strip_pem_headers(public_pem.decode('utf-8'))
            private_base64 = strip_pem_headers(private_pem.decode('utf-8'))

            # --- TẠO VOTER ---
            Voter.objects.create(
                user=request.user,
                public_key=public_base64,
                private_key_encrypted=private_base64
            )

            # --- LƯU VÀO SESSION ---
            request.session['newly_generated_public_key'] = public_base64
            request.session['newly_generated_private_key'] = private_base64

            return redirect('dangky_cutri_success')

        except Exception as e:
            messages.error(request, f'Đã có lỗi xảy ra khi sinh khóa: {e}')
            return redirect('dangky_cutri')

    return render(request, 'userpages/dangky_cutri.html')




def dangky_cutri_success(request):
    """
    Hiển thị khóa cho người dùng MỘT LẦN DUY NHẤT sau khi tạo.
    """
    # Lấy khóa từ session và xóa nó đi để không hiển thị lại
    public_key = request.session.pop('newly_generated_public_key', None)
    private_key = request.session.pop('newly_generated_private_key', None)

    # Nếu không có khóa trong session (người dùng vào thẳng URL), chuyển về trang chủ
    if not public_key or not private_key:
        return redirect('user')

    context = {
        'public_key': public_key,
        'private_key': private_key,
    }
    return render(request, 'userpages/dangky_cutri_success.html', context)

from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone


def bo_phieu(request, id):
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.error(request, 'Bạn cần đăng nhập để bỏ phiếu.')
            return redirect('login')

        try:
            ballot = get_object_or_404(Ballot, pk=id)
            voter = request.user.voter
            now = timezone.now()

            if not (ballot.start_date <= now <= ballot.end_date):
                messages.error(request, 'Cuộc bầu cử này không còn hiệu lực.')
                return redirect('chitiet_baucu_u', id=id)

            if Vote.objects.filter(ballot=ballot, voter_public_key=voter.public_key).exists():
                messages.warning(request, 'Bạn đã bỏ phiếu rồi.')
                return redirect('chitiet_baucu_u', id=id)

            candidate_id = request.POST.get('candidate')
            if not candidate_id:
                messages.error(request, 'Bạn chưa chọn ứng cử viên.')
                return redirect('chitiet_baucu_u', id=id)

            candidate = get_object_or_404(Candidate, pk=candidate_id, ballot=ballot)

            Vote.objects.create(
                ballot=ballot,
                candidate=candidate,
                voter_public_key=voter.public_key
            )

            messages.success(request, 'Bỏ phiếu thành công!')
            return redirect('chitiet_baucu_u', id=id)

        except Exception as e:
            messages.error(request, f'Lỗi khi bỏ phiếu: {e}')
            return redirect('chitiet_baucu_u', id=id)

    return redirect('chitiet_baucu_u', id=id)
