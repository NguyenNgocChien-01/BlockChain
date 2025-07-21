import json
import hashlib
import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from quanly.models import Ballot, Block, Vote

# Định nghĩa thư mục lưu trữ các file blockchain.json
# Thư mục này sẽ được tạo ngang hàng với file manage.py của dự án Django.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLOCKCHAIN_EXPORT_DIR = os.path.join(BASE_DIR, 'save_blockchain') 

class Command(BaseCommand):
    help = 'Thực hiện đào các khối mới cho các cuộc bầu cử có phiếu chờ và xuất toàn bộ blockchain ra một file JSON duy nhất cho mỗi cuộc bầu cử.'

    # Định nghĩa các hằng số cho tiêu chí tạo khối
    MIN_VOTES_PER_BLOCK = 1   # Số phiếu bầu tối thiểu để tạo một khối mới
    MAX_BLOCK_INTERVAL_SECONDS = 300 # Khoảng thời gian tối đa (giây) giữa các khối (5 phút)

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Bắt đầu quá trình đào khối và xuất dữ liệu blockchain...'))

        # Đảm bảo thư mục xuất khẩu tồn tại
        if not os.path.exists(BLOCKCHAIN_EXPORT_DIR):
            os.makedirs(BLOCKCHAIN_EXPORT_DIR)
            self.stdout.write(self.style.WARNING(f"Đã tạo thư mục xuất dữ liệu: {BLOCKCHAIN_EXPORT_DIR}"))

        # Lấy tất cả các cuộc bầu cử (hoặc những cuộc có thể có phiếu chờ)
        all_ballots = Ballot.objects.all()

        if not all_ballots.exists():
            self.stdout.write(self.style.WARNING("Không tìm thấy cuộc bầu cử nào để xử lý blockchain."))
            return

        for ballot in all_ballots:
            self.stdout.write(f"\nĐang xử lý Cuộc Bầu Cử: {ballot.title} (ID: {ballot.id})")
            
            # Lấy các phiếu bầu chưa được gán vào khối cho cuộc bầu cử hiện tại
            pending_votes = Vote.objects.filter(ballot=ballot, block__isnull=True).order_by('timestamp')
            num_pending_votes = pending_votes.count()

            last_block = Block.objects.filter(ballot=ballot).order_by('-id').first() # Lấy khối cuối cùng theo ID giảm dần
            
            should_mine_new_block = False

            # Tiêu chí 1: Nếu đây là khối đầu tiên (Genesis Block) và có phiếu bầu chờ
            if not last_block and num_pending_votes > 0:
                should_mine_new_block = True
                self.stdout.write(f"  Cần tạo khối đầu tiên (Genesis Block) cho cuộc bầu cử này.")
            # Tiêu chí 2: Đủ số lượng phiếu bầu tối thiểu
            elif num_pending_votes >= self.MIN_VOTES_PER_BLOCK:
                should_mine_new_block = True
                self.stdout.write(f"  Có {num_pending_votes} phiếu chờ. Đã đạt số phiếu bầu tối thiểu để tạo khối ({self.MIN_VOTES_PER_BLOCK}).")
            # Tiêu chí 3: Đã quá thời gian tối đa kể từ khối cuối cùng (nếu có khối cuối cùng)
            elif last_block and (timezone.now() - last_block.timestamp).total_seconds() >= self.MAX_BLOCK_INTERVAL_SECONDS:
                should_mine_new_block = True
                time_since_last_block = (timezone.now() - last_block.timestamp).total_seconds() / 60
                self.stdout.write(f"  Thời gian kể từ khối cuối cùng: {time_since_last_block:.2f} phút. Đã vượt quá khoảng thời gian tối đa ({self.MAX_BLOCK_INTERVAL_SECONDS/60} phút).")

            if should_mine_new_block:
                self.stdout.write(f"  Đang khởi tạo tạo khối mới...")
                
                try:
                    with transaction.atomic(): # Đảm bảo tính toàn vẹn dữ liệu giao dịch database
                        # Tạo khối mới
                        new_block = Block.objects.create(
                            ballot=ballot,
                            previous_hash=last_block.hash if last_block else '0', # '0' cho genesis block (khối khởi thủy)
                            difficulty=4 # Có thể lấy độ khó từ cài đặt hoặc từ Ballot model
                        )
                        
                        # Gán TẤT CẢ các phiếu bầu đang chờ vào khối mới
                        for vote in pending_votes:
                            vote.block = new_block
                            vote.save()
                        
                        # Thực hiện đào khối (Proof of Work)
                        # Phương thức mine_block() của bạn đã tự động gọi save() sau khi đào xong.
                        new_block.mine_block()
                        
                        self.stdout.write(self.style.SUCCESS(f"  ✅ Đã đào và lưu thành công Khối #{new_block.id} cho Cuộc Bầu Cử '{ballot.title}'"))
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  ❌ Lỗi khi đào khối cho Cuộc Bầu Cử '{ballot.title}': {e}"))
                    # transaction.atomic() sẽ tự động rollback nếu có lỗi, không cần xử lý thêm ở đây.
                    continue # Chuyển sang cuộc bầu cử tiếp theo nếu có lỗi

            else:
                self.stdout.write(f"  Các điều kiện chưa đủ để đào khối mới cho Cuộc Bầu Cử '{ballot.title}'. Số phiếu chờ: {num_pending_votes}")
            
            # --- BẮT ĐẦU PHẦN LƯU VÀO FILE JSON DUY NHẤT ---
            self.export_blockchain_to_json_file(ballot)

        self.stdout.write(self.style.SUCCESS('\nQuá trình đào khối và xuất dữ liệu blockchain đã hoàn tất.'))

    def export_blockchain_to_json_file(self, ballot):
        """
        Xuất tất cả các khối (Block) của một cuộc bầu cử cụ thể ra file JSON duy nhất.
        """
        self.stdout.write(f"  Đang xuất dữ liệu blockchain cho Cuộc Bầu Cử '{ballot.title}'...")
        
        # Lấy tất cả các khối thuộc cuộc bầu cử này, sắp xếp theo ID tăng dần
        blocks = Block.objects.filter(ballot=ballot).order_by('id')
        
        if not blocks.exists():
            self.stdout.write(self.style.WARNING(f"    Không tìm thấy khối nào cho Cuộc Bầu Cử '{ballot.title}'. Bỏ qua việc xuất file."))
            return

        blockchain_data = []
        for block in blocks:
            blockchain_data.append(block.to_json_serializable())
        
        # Tính toán "chain_hash" của toàn bộ chuỗi
        # Đảm bảo dữ liệu được sắp xếp để hash luôn nhất quán
        full_chain_string = json.dumps(blockchain_data, ensure_ascii=False, sort_keys=True)
        chain_hash = hashlib.sha256(full_chain_string.encode('utf-8')).hexdigest()
        
        # Định dạng dữ liệu cuối cùng cho file JSON
        final_json_output = {
            "chain_hash": chain_hash,
            "length": len(blockchain_data),
            "blocks": blockchain_data
        }
        
        # Tạo tên file: Ví dụ: blockchain_cuoc_bau_cu_a_1.json
        # Thay thế các ký tự không hợp lệ trong tên file để đảm bảo tương thích trên mọi hệ điều hành.
        safe_ballot_title = ballot.title.replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_').lower()
        file_name = f"blockchain_{safe_ballot_title}_{ballot.id}.json"
        file_path = os.path.join(BLOCKCHAIN_EXPORT_DIR, file_name)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(final_json_output, f, indent=4, ensure_ascii=False)
            self.stdout.write(self.style.SUCCESS(f"    ✅ Đã xuất blockchain ra: {file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"    ❌ Lỗi khi xuất blockchain ra {file_path}: {e}"))