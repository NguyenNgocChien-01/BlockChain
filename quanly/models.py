import hashlib
import os
import time
import uuid
from django.db import models
from django.utils import timezone

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
    """Bảng chứa thông tin về một cuộc bầu cử cụ thể."""
    title = models.CharField("Tiêu đề cuộc bầu cử", max_length=255)
    description = models.TextField("Mô tả", null=True, blank=True)
    start_date = models.DateTimeField("Thời gian bắt đầu")
    end_date = models.DateTimeField("Thời gian kết thúc")

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
    private_key_encrypted = models.TextField("Khóa bí mật đã mã hóa")

    class Meta:
        verbose_name = "Cử Tri"
        verbose_name_plural = "Các Cử Tri"

    def __str__(self):
        return self.user.username

class Block(models.Model):
    # CÁC TRƯỜNG LƯU TRỮ DỮ LIỆU
    ballot = models.ForeignKey('Ballot', on_delete=models.CASCADE, verbose_name="Cuộc bầu cử")
    previous_hash = models.CharField("Hash Khối Trước", max_length=64, null=True, blank=True)
    timestamp = models.DateTimeField("Dấu thời gian", default=timezone.now)
    difficulty = models.IntegerField("Độ khó")
    nonce = models.BigIntegerField("Nonce", default=0) # Dùng BigIntegerField cho nonce lớn
    hash = models.CharField("Hash", max_length=64, unique=True, null=True, blank=True)

    class Meta:
        verbose_name = "Khối"
        verbose_name_plural = "Các Khối"
        ordering = ['-id'] # Sắp xếp theo ID giảm dần (mới nhất lên đầu)

    # CÁC PHƯƠNG THỨC LOGIC
    def get_vote_data_string(self):
        """
        Lấy dữ liệu từ các phiếu bầu liên quan và tạo thành một chuỗi ổn định.
        Đây là cách thay thế cho thuộc tính 'data' trong class Python thuần.
        """
        # self.votes.all() hoạt động vì có 'related_name' trong ForeignKey của model Vote
        votes = self.votes.all().order_by('id') 
        return "".join([str(v.id) for v in votes])

    def calculate_hash(self):
        """Tính toán hash dựa trên toàn bộ các thuộc tính của khối."""
        vote_data = self.get_vote_data_string()
        # Dùng self.id thay cho index
        value = f"{self.id}{self.timestamp}{vote_data}{self.previous_hash}{self.difficulty}{self.nonce}"
        return hashlib.sha256(value.encode()).hexdigest()

    def mine_block(self):
        """
        Thực hiện cơ chế Proof of Work để tìm ra hash hợp lệ và lưu vào database.
        """
        print(f"Bắt đầu đào block #{self.id} với độ khó {self.difficulty}...")
        prefix_str = '0' * self.difficulty
        start_time = time.time()

        while True:
            hash_value = self.calculate_hash()
            if hash_value.startswith(prefix_str):
                end_time = time.time()
                
                # Cập nhật hash và nonce cho đối tượng model
                self.hash = hash_value
                
                # Quan trọng: Lưu lại các thay đổi vào database
                self.save()
                
                print(f"✅ Đào thành công block #{self.id}!")
                print(f"   Hash: {self.hash}")
                print(f"   Nonce: {self.nonce}")
                print(f"   Thời gian đào: {end_time - start_time:.4f} giây\n")
                return self.hash
            else:
                self.nonce += 1
    
    def __str__(self):
            return f"Block #{self.id} - Ballot: {self.ballot.title}"

class Vote(models.Model):
    """Bảng đại diện cho mỗi phiếu bầu, hoạt động như một giao dịch (transaction)."""
    ballot = models.ForeignKey(Ballot, on_delete=models.CASCADE, verbose_name="Cuộc bầu cử")
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, verbose_name="Ứng viên")
    block = models.ForeignKey(
        Block, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True, 
        verbose_name="Thuộc khối",
        related_name='votes' # Thêm dòng này
    )
    
    # Dữ liệu mã hóa để đảm bảo tính toàn vẹn và xác thực
    voter_public_key = models.TextField("Khóa công khai của cử tri")
    signature = models.TextField("Chữ ký số")
    timestamp = models.DateTimeField("Dấu thời gian", auto_now_add=True)
    
    class Meta:
        verbose_name = "Phiếu Bầu (Vote)"
        verbose_name_plural = "Các Phiếu Bầu (Votes)"

    def __str__(self):
        return f"Phiếu cho {self.candidate.name}"


