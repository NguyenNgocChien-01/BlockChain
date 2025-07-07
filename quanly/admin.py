from django.contrib import admin

from .models import *
admin.site.register(Ballot)
admin.site.register(Voter)
admin.site.register(Vote)
admin.site.register(Block)
admin.site.register(Candidate)

# Register your models here.
