

from django.urls import include, path

from quanly import admin
from quanly.views import *
from quanly import views

urlpatterns = [
    path('',trangchu,name='trangchu'),
    path('chart/',chart,name='chart'),
    path('baucu/',baucu,name='baucu'),
    path('baucu/add/', add_baucu, name='add_baucu'),
    path('baucu/delete/<int:id>/', delete_baucu, name='delete_baucu'),
    path('baucu/edit/<int:id>/', edit_baucu, name='edit_baucu'),
    path('baucu/chitiet/<int:id>',chitiet_baucu, name='chitiet_baucu'),
    path('baucu/<int:id>/ketthuc/', ketthuc_baucu, name='ketthuc_baucu'),
    path('baucu/delete_ungcuvien/<int:id>',delete_ungcuvien, name='delete_ungcuvien'),
    path('baucu/add_ungcuvien/<int:id>',add_ungcuvien, name='add_ungcuvien'),
    path('baucu/edit_ungcuvien/<int:id>',edit_ungcuvien, name='edit_ungcuvien'),
    path('ds_user/',ds_user,name='ds_user'),
    path('ds_user/add/', add_user, name='add_user'),
    path('ds_user/delete/<int:id>/', delete_user, name='delete_user'),
    path('ds_user/edit/<int:id>/', edit_user, name='edit_user'),
    path('ds_user/<int:user_id>/revoke-voter/', views.revoke_voter_status, name='revoke_voter_status'),
    path('ketqua/<int:id>/', views.ketqua_baucu, name='ketqua_baucu'),
    path('dsphieu/<int:ballot_id>/', danhsach_phieubau, name='danhsach_phieubau'),
    # path('baucu/dao_all/', dao_all_block, name='dao_all'),
    # path('baucu/dao-block/<int:id>/', dao_block , name='dao_block'),
    path('lichsu-change/', lichsu_change, name='lichsu_change'),



]