from django.urls import include, path

from user import admin
from user.views import *

urlpatterns = [
    path('',user,name='user'),
    path('baucu/',ds_baucu,name='baucu_u'),

]