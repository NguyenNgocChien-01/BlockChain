Hướng dẫn Cài đặt & Chạy
Clone repository về máy:

```bash
git clone https://github.com/NguyenNgocChien-01/BlockChain.git
cd BlockChain
pip install Django
```

### 1. Khởi động server:
```bash
python manage.py runserver
```


Tạo bầu cử --> Thêm ứng viên --> Đăng nhập user --> Đăng ký cử tri --> Vote (phải load file) --> Khi nào muốn lưu lên block thì qua admin hoặc chạy lệnh
### Lưu tất cả vote vào block
``` bash
python manage.py dao_block
````

### Lưu vote của ballot_id=1 và block (có check chain_hash)
``` bash
python manage.py dao_block --ballot-id 1
````

### Lưu vote của ballot_id=1 và block bỏ qua chain_hash cũ sau đó ghi đè nội dung
``` bash
python manage.py dao_block --ballot-id 1 --force-restore
````

File block được lưu riêng cho mỗi bầu cử trong quanly\save_blockchain

File chạy dòng lệnh được lưu trong quanly\management\commands

model lưu trong quanly/models.py

template lưu file html


