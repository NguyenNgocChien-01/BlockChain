from django.shortcuts import render

from quanly.models import *

# Create your views here.
def user(request):
    return render(request,'userpages/index.html')

# views.py
def ds_baucu(request):
    keyword = request.GET.get('keyword', '')
    if keyword:
        baucus = Ballot.objects.filter(title__icontains=keyword)
    else:
        baucus = Ballot.objects.all()

    context = {
        'baucus': baucus,
        'keyword': keyword,
    }
    # Render template mới dành cho user
    return render(request, 'userpages/baucu/baucu.html', context)