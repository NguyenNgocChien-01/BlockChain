from django.contrib import messages 
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q
from .models import *
from django.db.models import Count
from django.db import transaction
from .models import Ballot, Vote
from .blockchain_utils import get_blockchain_file_path
from django.core.management import call_command
import json
from collections import Counter
# Create your views here.
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
    }
    
    return render(request, 'adminpages/baucu/baucu.html', context)

def add_baucu(request):

    if request.method == "POST":

        tieude = request.POST.get('tieude')
        mota = request.POST.get('mota')
        tgbd = request.POST.get('start_date')
        tgkt = request.POST.get('end_date')
        maxchoice = request.POST.get('max_choice', 1)
        

        ballot_type = request.POST.get('type', 'PUBLIC')

    
        new_ballot = Ballot.objects.create(
            title=tieude,
            description=mota,
            start_date=tgbd,
            end_date=tgkt,
            type=ballot_type,
            max_choices=maxchoice
        )


        if ballot_type == 'PRIVATE':
            voter_ids = request.POST.getlist('eligible_voters')
            if voter_ids:
                new_ballot.eligible_voters.set(voter_ids)

    return redirect('baucu')

def delete_baucu(request, id):
    baucu = get_object_or_404(Ballot, id=id)
    baucu.delete()
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


    context = {
        'baucu': baucu,
        'ungcuviens': ungcuviens,
        'is_active': is_active,
        'eligible_voters_list': eligible_voters_list,
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
    """
    Hiển thị kết quả bầu cử bằng cách đọc và phân tích file JSON của blockchain,
    chỉ sau khi cuộc bầu cử đã kết thúc.
    """
    baucu = get_object_or_404(Ballot, id=id)

    # 1. Kiểm tra xem cuộc bầu cử đã kết thúc chưa
    if baucu.end_date > timezone.now():
        messages.warning(request, f"Cuộc bầu cử '{baucu.title}' vẫn đang diễn ra. Kết quả chỉ có thể xem sau khi kết thúc.")
        return redirect('baucu')

    ketqua_tu_file = []
    tong_so_phieu = 0
    
    # 2. Lấy đường dẫn đến file JSON blockchain
    filepath = get_blockchain_file_path(ballot_id=id, base_export_dir='quanly\save_blockchain')

    try:
        # 3. Đọc và phân tích file JSON để kiểm phiếu
        with open(filepath, 'r', encoding='utf-8') as f:
            blockchain_data = json.load(f)

        vote_counts = Counter()
        blocks = blockchain_data.get("blocks", [])

        for block in blocks:
            data_string = block.get("data", "")
            if "Genesis Block" in data_string or "No transactions" in data_string or not data_string:
                continue
            
            vote_summaries = data_string.split(';')
            
            for summary in vote_summaries:
                summary = summary.strip()
                if not summary: continue
                try:
                    # Tách chuỗi để lấy tên ứng viên
                    # Logic này sẽ lấy tất cả tên ứng viên trong một phiếu, ví dụ: "A, B"
                    name_part = summary.split(':')[1].split('(')[0].strip()
                    # Tách các tên nếu có nhiều lựa chọn trong một phiếu
                    candidate_names = [name.strip() for name in name_part.split(',')]
                    for name in candidate_names:
                        if name:
                            vote_counts[name] += 1
                except IndexError:
                    pass # Bỏ qua các dòng dữ liệu không đúng định dạng

        # 4. Chuẩn bị dữ liệu để hiển thị ra template
        sorted_results = vote_counts.most_common()
        tong_so_phieu = sum(vote_counts.values())
        
        for candidate_name, so_phieu in sorted_results:
            percentage = round((so_phieu / tong_so_phieu) * 100, 2) if tong_so_phieu > 0 else 0
            ketqua_tu_file.append({
                'candidate__name': candidate_name,
                'so_phieu': so_phieu,
                'phan_tram': percentage
            })

    except FileNotFoundError:
        messages.error(request, f"Không có phiếu bầu nào hết")
        return redirect('baucu')
    except Exception as e:
        messages.error(request, f"Lỗi khi đọc file blockchain: {e}")
        return redirect('baucu')
        
    # 5. Gửi dữ liệu đến template
    context = {
        'baucu': baucu,
        'ketqua': ketqua_tu_file,
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


# def dao_all_block(request):


#     try:
       
#         call_command('dao_block', '--force-mine','--force-restore')
        
#         messages.success(request, "Đã thực hiện đào khối thành công cho TẤT CẢ các cuộc bầu cử có phiếu chờ.")

#     except Exception as e:
#         messages.error(request, f"Đã có lỗi xảy ra trong quá trình đào khối: {e}")


#     return redirect('baucu')

# def dao_block(request, id):
#     try:
#         ballot = get_object_or_404(Ballot, pk=id)
        

#         call_command('dao_block', '--ballot-id', str(id))
#         messages.success(request,f"Đã lưu thành công các phiếu của {ballot.title}")
        

#     except Exception as e:
#         messages.error(request, f"Đã có lỗi xảy ra trong quá trình đào khối: {e}")

#     return redirect('baucu')


def lichsu_change(request):
    logs = UserTamperLog.objects.all().order_by('-timestamp')
    context = {
    'logs': logs,
}

    return render(request, 'adminpages/tamperlog.html', context)
    

