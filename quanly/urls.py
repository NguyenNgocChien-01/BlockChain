

from django.urls import include, path

from quanly import admin
from quanly.views import *

urlpatterns = [
    path('',trangchu,name='trangchu'),
    path('baucu/',baucu,name='baucu'),
    path('baucu/add/', add_baucu, name='add_baucu'),
    path('baucu/delete/<int:id>/', delete_baucu, name='delete_baucu'),
    path('baucu/edit/<int:id>/', edit_baucu, name='edit_baucu'),
    path('baucu/chitiet/<int:id>',chitiet_baucu, name='chitiet_baucu'),
    path('baucu/delete_ungcuvien/<int:id>',delete_ungcuvien, name='delete_ungcuvien'),
    path('baucu/add_ungcuvien/<int:id>',add_ungcuvien, name='add_ungcuvien'),
    path('baucu/edit_ungcuvien/<int:id>',edit_ungcuvien, name='edit_ungcuvien'),
]