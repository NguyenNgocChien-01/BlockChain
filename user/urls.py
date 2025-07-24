from django.urls import include, path

from user import admin
from user.views import *
from user.views import bo_phieu

urlpatterns = [
    path('',user,name='user'),
    path('login/',login,name='login'),
    path('logout/',logout,name='logout'),
    path('baucu/',ds_baucu,name='baucu_u'),
    path('baucu/chitiet/<int:id>',chitiet_baucu_u, name='chitiet_baucu_u'),
    path('cutri/',view_dangky_cutri, name='view_dangky_cutri'),
    path('cutri/save', dangky_cutri, name='dangky_cutri'),
    path('baucu/bo-phieu/<int:id>/', bo_phieu, name='bo_phieu'),
    path('baucu/<int:id>/my-vote/', my_vote, name='my_vote'),
    path('baucu/change-vote/<int:vote_id>/', change_vote, name='change_vote'),



]