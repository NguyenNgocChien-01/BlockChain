from django.contrib import messages 
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q
from .models import *
from django.db.models import Count
from django.db import transaction
from .models import Ballot, Vote

from django.core.management import call_command
# Create your views here.
def trangchu(request):
    return render(request,'adminpages/index.html')

def baucu(request):
    keyword = request.GET.get('keyword', '')
    baucus = Ballot.objects.all()
    
    if keyword:
        baucus = baucus.filter(
            Q(title__icontains=keyword) | Q(description__icontains=keyword)
        )
        
    context = {
        'baucus': baucus,
        'keyword': keyword, # Giữ lại keyword để hiển thị trên ô tìm kiếm
    }
    
    return render(request, 'adminpages/baucu/baucu.html', context)


def add_baucu(request):
    if request.method == "POST":
        tieude = request.POST.get('tieude')
        mota = request.POST.get('mota')
        tgbd = request.POST.get('start_date')
        tgkt = request.POST.get('end_date')

        Ballot.objects.create(
            title=tieude,
            description=mota,
            start_date=tgbd,
            end_date=tgkt
        )

    return redirect('baucu')  # Nếu không phải POST, quay lại danh sách

def delete_baucu(request, id):
    baucu = get_object_or_404(Ballot, id=id)
    # baucu.delete()
    return redirect('baucu') 

def edit_baucu(request, id):
    baucu = get_object_or_404(Ballot,id=id)
    if request.method == "POST":
        baucu.title = request.POST.get('tieude')
        baucu.description = request.POST.get('mota')
        baucu.start_date = request.POST.get('start_date')
        baucu.end_date = request.POST.get('end_date')
    baucu.save()
    return redirect('baucu') 

def chitiet_baucu(request, id):
    baucu = get_object_or_404(Ballot, id=id)
    ungcuviens = Candidate.objects.filter(ballot=baucu)

    now = timezone.now()

    is_active = baucu.start_date <= now and baucu.end_date >= now

    context = {
        'baucu': baucu,
        'ungcuviens': ungcuviens,
        'is_active': is_active, 
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

        username = request.POST.get('username')
        first_name = request.POST.get('firstname')
        last_name = request.POST.get('lastname')
        email = request.POST.get('email')
        password = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password != password2:
            return redirect('add_user')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Tên đăng nhập này đã tồn tại!')
            return redirect('add_user')


        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        

        messages.success(request, f'Tạo người dùng "{username}" thành công!')
        return redirect('ds_user') # Chuyển hướng về trang danh sách

        
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
    baucu = get_object_or_404(Ballot, id=id)


    if baucu.end_date > timezone.now():
        messages.warning(request, f"Cuộc bầu cử '{baucu.title}' vẫn đang diễn ra. Kết quả chỉ có thể được xem sau khi đã kết thúc.")
        return redirect('chitiet_baucu', id=id)


    ketqua = Vote.objects.filter(candidate__ballot=baucu)\
        .values('candidate__name')\
        .annotate(so_phieu=Count('id'))\
        .order_by('-so_phieu')

    tong_so_phieu = sum(item['so_phieu'] for item in ketqua)

    for item in ketqua:
        if tong_so_phieu > 0:
            item['phan_tram'] = round((item['so_phieu'] / tong_so_phieu) * 100, 2)
        else:
            item['phan_tram'] = 0

    context = {
        'baucu': baucu,
        'ketqua': ketqua,
        'tong_so_phieu': tong_so_phieu,
    }

    return render(request, 'adminpages/baucu/ketqua.html', context)

def danhsach_phieubau(request, ballot_id):

    ballot = get_object_or_404(Ballot, id=ballot_id)
    
   

    votes = Vote.objects.filter(ballot=ballot).order_by('timestamp') # Sắp xếp theo thời gian bỏ phiếu

    vote_details = []
    for vote in votes:
        voter_username = "Không xác định" # Mặc định
        try:
            voter_obj = Voter.objects.get(public_key=vote.voter_public_key)
            voter_username = voter_obj.user.username
        except Voter.DoesNotExist:
            pass 

        vote_details.append({
            'id': vote.id,
            'candidate_name': vote.candidate.name,
            'voter_public_key': vote.voter_public_key,
            'voter_username': voter_username, # Thêm username vào đây
            'signature': vote.signature,
            'timestamp': vote.timestamp,
            'block_id': vote.block.id if vote.block else 'Chưa vào khối'
        })
    
    context = {
        'ballot': ballot,
        'vote_details': vote_details, # Dữ liệu đã xử lý để hiển thị
    }
    

    return render(request, 'adminpages/baucu/danhsach_phieubau.html', context)


def dao_all_block(request):


    try:
       
        call_command('dao_block', '--force-mine','--force-restore')
        
        messages.success(request, "Đã thực hiện đào khối thành công cho TẤT CẢ các cuộc bầu cử có phiếu chờ.")

    except Exception as e:
        messages.error(request, f"Đã có lỗi xảy ra trong quá trình đào khối: {e}")


    return redirect('baucu')