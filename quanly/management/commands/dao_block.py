import json
import hashlib
import os
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.db.models import Exists, OuterRef, Q 
from quanly.models import Ballot, Block, Vote 

from quanly.blockchain_utils import (
    save_blockchain_to_json_with_integrity_check, 
    verify_blockchain_integrity, 
    get_blockchain_file_path 
)
import unicodedata


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLOCKCHAIN_EXPORT_DIR_PER_BALLOT = os.path.join(BASE_DIR, 'save_blockchain') 


class Command(BaseCommand):
    help = 'Thực hiện đào các khối mới cho các cuộc bầu cử có phiếu chờ và xuất toàn bộ blockchain ra một file JSON duy nhất cho mỗi cuộc bầu cử.'

    MIN_VOTES_PER_BLOCK = 1 
    MAX_BLOCK_INTERVAL_SECONDS = 300 

    def add_arguments(self, parser):
        parser.add_argument(
            '--ballot-id',
            type=int,
            help='Chỉ xử lý việc đào cho một cuộc bầu cử cụ thể theo ID.',
        )
        parser.add_argument(
            '--force-mine',
            action='store_true', 
            help='Bỏ qua các tiêu chí số phiếu tối thiểu và thời gian tối đa, đào một block mới ngay lập tức nếu có phiếu chờ.',
        )
        # Tùy chọn --no-export giờ chỉ ảnh hưởng đến việc xuất file RIÊNG LẺ
        parser.add_argument(
            '--no-export',
            action='store_true',
            help='Chỉ đào block, không xuất file JSON riêng cho cuộc bầu cử đó.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Bắt đầu quá trình đào khối và xuất dữ liệu blockchain...'))

        # Đảm bảo thư mục xuất khẩu cho từng cuộc bầu cử tồn tại
        if not os.path.exists(BLOCKCHAIN_EXPORT_DIR_PER_BALLOT):
            os.makedirs(BLOCKCHAIN_EXPORT_DIR_PER_BALLOT)
            self.stdout.write(self.style.WARNING(f"Đã tạo thư mục xuất dữ liệu từng cuộc bầu cử: {BLOCKCHAIN_EXPORT_DIR_PER_BALLOT}"))


        # Lọc theo ballot_id nếu được cung cấp
        if options['ballot_id']:
            ballots_to_process = Ballot.objects.filter(id=options['ballot_id'])
            if not ballots_to_process.exists():
                self.stdout.write(self.style.ERROR(f"Không tìm thấy cuộc bầu cử với ID: {options['ballot_id']}"))
                return
            self.stdout.write(self.style.SUCCESS(f"Chỉ xử lý cuộc bầu cử ID: {options['ballot_id']}"))
        else:
            # Lấy tất cả các cuộc bầu cử có ít nhất một phiếu bầu đang chờ HOẶC đã có ít nhất một block
            ballots_to_process = Ballot.objects.annotate(
                has_pending_votes=Exists(Vote.objects.filter(ballot=OuterRef('pk'), block__isnull=True)),
                has_existing_blocks=Exists(Block.objects.filter(ballot=OuterRef('pk')))
            ).filter(Q(has_pending_votes=True) | Q(has_existing_blocks=True)).distinct()

        if not ballots_to_process.exists():
            self.stdout.write(self.style.WARNING("Không tìm thấy cuộc bầu cử nào có phiếu chờ hoặc block đã tồn tại để xử lý."))
            self.stdout.write(self.style.SUCCESS('\nQuá trình đào khối và xuất dữ liệu blockchain đã hoàn tất.'))
            return # Thoát nếu không có gì để xử lý

        for ballot in ballots_to_process:
            pending_votes = Vote.objects.filter(ballot=ballot, block__isnull=True).order_by('timestamp')
            num_pending_votes = pending_votes.count()
            last_block = Block.objects.filter(ballot=ballot).order_by('-id').first() 
            
            should_mine_new_block = False

            # ĐIỀU CHỈNH LOGIC ĐÀO BLOCK Ở ĐÂY
            # Tiêu chí 1: Nếu đây là khối đầu tiên (Genesis Block) và có phiếu bầu chờ
            if not last_block and num_pending_votes > 0:
                should_mine_new_block = True
                self.stdout.write(f"  Cuộc Bầu Cử '{ballot.title}': Cần tạo khối đầu tiên (Genesis Block) với {num_pending_votes} phiếu chờ.")
            # Tiêu chí 2: Đủ số lượng phiếu bầu tối thiểu
            elif num_pending_votes >= self.MIN_VOTES_PER_BLOCK:
                should_mine_new_block = True
                self.stdout.write(f"  Cuộc Bầu Cử '{ballot.title}': Có {num_pending_votes} phiếu chờ. Đã đạt số phiếu bầu tối thiểu ({self.MIN_VOTES_PER_BLOCK}).")
            # Tiêu chí 3: Đã quá thời gian tối đa kể từ khối cuối cùng VÀ CÓ PHIẾU BẦU CHỜ
            elif last_block and num_pending_votes > 0 and (timezone.now() - last_block.timestamp).total_seconds() >= self.MAX_BLOCK_INTERVAL_SECONDS:
                should_mine_new_block = True
                time_since_last_block_min = (timezone.now() - last_block.timestamp).total_seconds() / 60
                self.stdout.write(f"  Cuộc Bầu Cử '{ballot.title}': Có {num_pending_votes} phiếu chờ. Thời gian kể từ khối cuối cùng: {time_since_last_block_min:.2f} phút. Đã vượt quá khoảng thời gian tối đa ({self.MAX_BLOCK_INTERVAL_SECONDS/60} phút).")
            # Tiêu chí 4: Force mine được bật VÀ CÓ PHIẾU BẦU CHỜ
            elif options['force_mine'] and num_pending_votes > 0:
                should_mine_new_block = True
                self.stdout.write(self.style.WARNING(f"  Cờ --force-mine được bật cho Cuộc Bầu Cử '{ballot.title}'. Đào block mới dù không đủ tiêu chí khác."))
            else:
                # Nếu không đủ điều kiện để đào, in thông báo rõ ràng và bỏ qua
                self.stdout.write(f"  Cuộc Bầu Cử '{ballot.title}': Không đủ điều kiện để đào khối mới (số phiếu chờ: {num_pending_votes}).")
                continue # Chuyển sang cuộc bầu cử tiếp theo


            if should_mine_new_block: # Chỉ thực hiện phần đào nếu điều kiện trên là True
                self.stdout.write(f"  Đang khởi tạo tạo khối mới...") 
                
                try:
                    with transaction.atomic():
                        new_block = Block.objects.create(
                            ballot=ballot,
                            previous_hash=last_block.hash if last_block else '0', 
                            difficulty=2
                        )
                        for vote in pending_votes:
                            vote.block = new_block
                            vote.save()
                        new_block.mine_block() # Hàm này đã lưu Block vào DB
                        
                        self.stdout.write(self.style.SUCCESS(f"   Đã đào và lưu thành công Khối #{new_block.id} với {num_pending_votes} phiếu bầu."))
                        
                        # --- XUẤT BLOCKCHAIN RIÊNG CHO TỪNG CUỘC BẦU CỬ ---
                        if not options['no_export']: # Chỉ xuất nếu cờ --no-export không được bật
                             # Sử dụng hàm từ blockchain_utils để lưu file JSON riêng cho ballot này
                            # BLOCKCHAIN_EXPORT_DIR_PER_BALLOT đã được định nghĩa ở đầu file
                            success_per_ballot, msg_per_ballot = save_blockchain_to_json_with_integrity_check(ballot.id, base_export_dir=BLOCKCHAIN_EXPORT_DIR_PER_BALLOT)
                            if success_per_ballot:
                                self.stdout.write(self.style.SUCCESS(f"   Đã xuất blockchain riêng cho '{ballot.title}': {msg_per_ballot}"))
                            else:
                                self.stdout.write(self.style.ERROR(f"   Lỗi khi xuất blockchain riêng cho '{ballot.title}': {msg_per_ballot}"))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   Lỗi khi đào khối cho Cuộc Bầu Cử '{ballot.title}': {e}"))
                    continue 

        # Phần cuối của hàm handle, sau khi vòng lặp for kết thúc
        self.stdout.write(self.style.SUCCESS('\nQuá trình đào khối và xuất dữ liệu blockchain đã hoàn tất.'))

