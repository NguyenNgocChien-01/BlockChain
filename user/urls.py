from django.urls import include, path

from user import admin
from user.views import *

urlpatterns = [
    path('',user,name='user'),
    path('login/',login,name='login'),
    path('logout/',logout,name='logout'),
    path('baucu/',ds_baucu,name='baucu_u'),
    path('baucu/chitiet/<int:id>',chitiet_baucu_u, name='chitiet_baucu_u'),
    path('cutri/',view_dangky_cutri, name='view_dangky_cutri'),
    path('cutri/save', dangky_cutri, name='dangky_cutri'),
    path('cutri/key', dangky_cutri_success, name='dangky_cutri_success')


]