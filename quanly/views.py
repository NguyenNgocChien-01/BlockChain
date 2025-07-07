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