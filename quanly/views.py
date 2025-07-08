from django.contrib import messages 
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q
from .models import *

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

def chitiet_baucu(request,id):
    baucu = get_object_or_404(Ballot,id=id)
    ungcuviens = Candidate.objects.filter(ballot=baucu)

    context = {
        'baucu': baucu,
        'ungcuviens':ungcuviens
    }
    
    return render(request,'adminpages/baucu/chitiet.html',context)

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
    users = User.objects.filter(
            Q(username__icontains=keyword) | Q(email__icontains=keyword) |
            Q(first_name__icontains=keyword) | Q(last_name__icontains=keyword)
        )
    
    if keyword:
        users = users.all()
        
    context = {
        'users': users,
        'keyword': keyword, # Giữ lại keyword để hiển thị trên ô tìm kiếm
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