import hashlib
import os
import time
import uuid
from django.db import models
from django.utils import timezone
from django.utils.timezone import localtime

# Create your models here.
from django.db import models
from django.contrib.auth.models import User

def candidate_avatar_path(instance, filename):

    # Lấy phần mở rộng của file (ví dụ: .jpg, .png)
    ext = os.path.splitext(filename)[1]
    # Tạo tên file mới bằng uuid4
    new_filename = f"{uuid.uuid4()}{ext}"
    # Trả về đường dẫn hoàn chỉnh
    return os.path.join('avatars', new_filename)


class Ballot(models.Model):
    BALLOT_TYPE_CHOICES = [
        ('PUBLIC', 'Công khai'),  # Bất kỳ ai cũng có thể tham gia
        ('PRIVATE', 'Riêng tư'), # Chỉ những người được chọn mới có thể tham gia
    ]
    title = models.CharField("Tiêu đề cuộc bầu cử", max_length=255)
    description = models.TextField("Mô tả", null=True, blank=True)
    start_date = models.DateTimeField("Thời gian bắt đầu")
    end_date = models.DateTimeField("Thời gian kết thúc")
    max_choices = models.PositiveIntegerField(default=1)

    type = models.CharField(
        "Loại hình",
        max_length=10,
        choices=BALLOT_TYPE_CHOICES,
        default='PUBLIC' # Mặc định là công khai
    )
    eligible_voters = models.ManyToManyField(
        'Voter',
        verbose_name="Cử tri được phép (cho bầu cử riêng tư)",
        blank=True, 
        related_name="private_ballots"
        )
    council_members = models.ManyToManyField(
        User, 
        verbose_name="Thành viên Hội đồng Kiểm phiếu",
        related_name="councils", 
        blank=True
    )
    threshold = models.IntegerField(
        "Ngưỡng giải mã",
        default=2,
        help_text="Số lượng thành viên tối thiểu cần thiết để giải mã phiếu bầu."
    )

    council_public_key = models.TextField(
        "Khóa Công khai Hội đồng", 
        null=True, 
        blank=True
    )

    
    class Meta:
        verbose_name = "Cuộc Bầu Cử"
        verbose_name_plural = "Các Cuộc Bầu Cử"

    
    def __str__(self):
        return self.title

class Candidate(models.Model):
    """Bảng chứa thông tin các ứng viên, thuộc về một cuộc bầu cử."""
    ballot = models.ForeignKey(Ballot, on_delete=models.CASCADE, verbose_name="Cuộc bầu cử")
    name = models.CharField("Tên ứng viên", max_length=255)
    avatar = models.ImageField(
        "Ảnh đại diện",
        upload_to=candidate_avatar_path, # Thư mục lưu ảnh trong media
        null=True, # Cho phép giá trị null trong CSDL
        blank=True # Cho phép trường này được để trống trong form
    )
    description = models.TextField("Mô tả", blank=True) # Thêm trường mô tả

    class Meta:
        verbose_name = "Ứng Viên"
        verbose_name_plural = "Các Ứng Viên"

    def __str__(self):
        return self.name

class Voter(models.Model):
    """Mở rộng User mặc định để lưu khóa công khai cho mỗi cử tri."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Người dùng")
    public_key = models.TextField("Khóa công khai", unique=True)
    # private_key_encrypted = models.TextField("Khóa bí mật đã mã hóa") # Đã xóa
    # salt = models.CharField("Salt cho mã hóa khóa bí mật", max_length=32, blank=True, null=True) # Đã xóa

    class Meta:
        verbose_name = "Cử Tri"
        verbose_name_plural = "Các Cử Tri"

    def __str__(self):
        return self.user.username



class Vote(models.Model):
    """Bảng đại diện cho mỗi phiếu bầu, hoạt động như một giao dịch (transaction)."""
    ballot = models.ForeignKey(Ballot, on_delete=models.CASCADE, verbose_name="Cuộc bầu cử")
    candidates = models.ManyToManyField(Candidate, verbose_name="Các ứng viên đã bầu", null=True,blank=True )
    encrypted_vote_data = models.TextField("Dữ liệu phiếu bầu đã mã hóa")
    # Dữ liệu mã hóa để đảm bảo tính toàn vẹn và xác thực
    voter_public_key = models.TextField("Khóa công khai của cử tri")
    signature = models.TextField("Chữ ký số")
    timestamp = models.DateTimeField("Dấu thời gian", auto_now_add=True)
    
    class Meta:
        verbose_name = "Phiếu Bầu (Vote)"
        verbose_name_plural = "Các Phiếu Bầu (Votes)"

    def __str__(self):
        # Hiển thị thông tin không phụ thuộc vào nội dung đã mã hóa
        return f"Phiếu bầu mã hóa #{self.id} cho '{self.ballot.title}'"
    


class UserTamperLog(models.Model):

    description = models.TextField("Mô tả chi tiết sự việc")
    timestamp = models.DateTimeField("Thời gian phát hiện", auto_now_add=True)
    
    attempted_by = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="Người thực hiện", null=True, blank=True)
    # Từ đâu?
    ip_address = models.GenericIPAddressField("Địa chỉ IP", null=True, blank=True)
    # Liên quan đến cuộc bầu cử nào?
    ballot = models.ForeignKey('Ballot', on_delete=models.PROTECT, verbose_name="Cuộc bầu cử liên quan", null=True, blank=True)
    # Chi tiết thay đổi (ví dụ: từ ứng viên A sang B)
    details = models.JSONField("Chi tiết thay đổi", null=True, blank=True)
    # Bằng chứng backup (nếu có)
    backup_file_path = models.CharField("Đường dẫn file backup", max_length=512, null=True, blank=True)

    class Meta:
        verbose_name = "Lịch Sử Sửa Phiếu"
        verbose_name_plural = "Các Lịch Sử Sửa Phiếu"

    def __str__(self):
        user_info = f"bởi {self.attempted_by.username}" if self.attempted_by else "bởi Hệ thống"
        return f"Cảnh báo lúc {self.timestamp.strftime('%d/%m/%Y %H:%M')} {user_info}"



class SubmittedKeyShare(models.Model):
    """
    Lưu trữ các mảnh khóa bí mật đã được nộp bởi thành viên Hội đồng
    cho một cuộc bầu cử cụ thể.
    """
    ballot = models.ForeignKey(Ballot, on_delete=models.CASCADE, related_name="submitted_shares")
    council_member = models.ForeignKey(User, on_delete=models.CASCADE)
    key_share = models.TextField("Mảnh khóa bí mật đã nộp")
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Đảm bảo mỗi thành viên chỉ có thể nộp 1 mảnh khóa cho 1 cuộc bầu cử
        unique_together = ('ballot', 'council_member')
        verbose_name = "Mảnh khóa Đã nộp"
        verbose_name_plural = "Các Mảnh khóa Đã nộp"

    def __str__(self):
        return f"Mảnh khóa của {self.council_member.username} cho '{self.ballot.title}'"
