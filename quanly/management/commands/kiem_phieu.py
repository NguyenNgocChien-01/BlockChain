# BauCuProject\quanly\management\commands\kiem_phieu.py

import json
import os
from collections import Counter
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone # Thêm import timezone
from quanly.models import Ballot # Thêm import Ballot

# Định nghĩa đường dẫn tới thư mục gốc của project
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BLOCKCHAIN_DIR = os.path.join(BASE_DIR, 'quanly\save_blockchain')

class Command(BaseCommand):
    help = 'Kiểm tra và chỉ kiểm phiếu từ file JSON nếu cuộc bầu cử đã kết thúc.'

    def add_arguments(self, parser):
        parser.add_argument('json_filename', type=str, help='Chỉ cần nhập TÊN file JSON trong thư mục save_blockchain.')

    def handle(self, *args, **options):
        filename = options['json_filename']
        filepath = os.path.join(BLOCKCHAIN_DIR, filename)

    
        try:
            # Ví dụ: "blockchain_bau_cu_c_8.json" -> "8"
            base_name = filename.split('.')[0]
            ballot_id_str = base_name.split('_')[-1]
            ballot_id = int(ballot_id_str)
        except (IndexError, ValueError):
            raise CommandError("Lỗi: Tên file không đúng định dạng. Không thể trích xuất ID cuộc bầu cử.")

        try:
            ballot = Ballot.objects.get(pk=ballot_id)
            if ballot.end_date > timezone.now():
                raise CommandError(f"Lỗi: Cuộc bầu cử '{ballot.title}' vẫn đang diễn ra. "
                                   f"Kết quả chỉ có thể được kiểm từ sau ngày {ballot.end_date.strftime('%d-%m-%Y %H:%M')}.")
            self.stdout.write(self.style.SUCCESS(f"Xác nhận: Cuộc bầu cử '{ballot.title}' đã kết thúc. Bắt đầu kiểm phiếu..."))
        except Ballot.DoesNotExist:
            raise CommandError(f"Lỗi: Không tìm thấy cuộc bầu cử với ID={ballot_id} trong cơ sở dữ liệu.")


        self.stdout.write(f"Đọc dữ liệu từ file: {filepath}")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"Lỗi: Không tìm thấy file tại '{filepath}'.")
        except json.JSONDecodeError:
            raise CommandError(f"Lỗi: File '{filepath}' không phải là định dạng JSON hợp lệ.")

        vote_counts = Counter()
        blocks = data.get("blocks", [])
        for block in blocks:
            data_string = block.get("data", "")
            if "Genesis Block" in data_string or not data_string or "No transactions" in data_string:
                continue
            
            vote_summaries = data_string.split(';')
            for summary in vote_summaries:
                summary = summary.strip()
                if not summary:
                    continue
                try:
                    name_part = summary.split(':')[1].split('(')[0].strip()
                    vote_counts[name_part] += 1
                except IndexError:
                    self.stdout.write(self.style.WARNING(f"Cảnh báo: Bỏ qua dòng dữ liệu không đúng định dạng: '{summary}'"))

        self.stdout.write(self.style.SUCCESS("\n--- KẾT QUẢ KIỂM PHIẾU TỪ FILE JSON ---"))
        self.stdout.write(f"Cuộc bầu cử: {data.get('ballot_title', 'Không rõ')}")
        self.stdout.write("-" * 40)
        if not vote_counts:
            self.stdout.write("Không tìm thấy phiếu bầu hợp lệ nào để đếm.")
            return
        sorted_results = vote_counts.most_common()
        total_votes = sum(vote_counts.values())
        self.stdout.write(f"Tổng số phiếu đã đếm: {total_votes}\n")
        self.stdout.write(f"{'Hạng':<5} {'Ứng Cử Viên':<25} {'Số Phiếu':<10}")
        self.stdout.write(f"{'-'*4:<5} {'-'*24:<25} {'-'*9:<10}")
        for i, (candidate, count) in enumerate(sorted_results, 1):
            self.stdout.write(f"{i:<5} {candidate:<25} {count:<10}")
        self.stdout.write(self.style.SUCCESS("\n--- Hoàn tất kiểm phiếu ---"))