from django.contrib import admin
from .models import *

@admin.register(Ballot)
class BallotAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'start_date', 'end_date')
    list_filter = ('type', 'start_date')
    search_fields = ('title', 'description')
    
    # Dùng filter_horizontal để giao diện chọn cử tri thân thiện hơn
    filter_horizontal = ('eligible_voters',)

    # Tùy chỉnh form để hiển thị các trường một cách logic
    fieldsets = (
        (None, {
            'fields': ('title', 'description')
        }),
        ('Thời gian', {
            'fields': ('start_date', 'end_date')
        }),
        ('Cài đặt Nâng cao', {
            'classes': ('collapse',), # Có thể thu gọn lại
            'fields': ('type', 'eligible_voters'),
        }),
    )
    
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        # Gợi ý: Bạn có thể thêm JavaScript ở đây để ẩn/hiện trường 'eligible_voters'
        # dựa trên giá trị của trường 'type' để trải nghiệm tốt hơn.
        return fieldsets
from .models import *
# admin.site.register(Ballot)
admin.site.register(Voter)
admin.site.register(Vote)
# admin.site.register(Block)
admin.site.register(Candidate)
admin.site.register(UserTamperLog)

# Register your models here.
