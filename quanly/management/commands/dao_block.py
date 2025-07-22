# quanly/management/commands/mine_and_export.py

import json
import hashlib
import os
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.db.models import Exists, OuterRef, Q 
from quanly.models import Ballot, Block, Vote 

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BLOCKCHAIN_EXPORT_DIR_PER_BALLOT = os.path.join(BASE_DIR, 'save_blockchain') 

from quanly.blockchain_utils import (
    save_blockchain_to_json_with_integrity_check, 
    verify_blockchain_integrity, 
    get_blockchain_file_path 
)
import unicodedata




class Command(BaseCommand):
    help = 'Chỉ đào khối và xuất file cho các cuộc bầu cử đã kết thúc.'
    

    def add_arguments(self, parser):
        parser.add_argument('--ballot-id', type=int)
        # Giữ lại force-mine để admin có thể chủ động chốt sổ thủ công nếu muốn
        parser.add_argument('--force-mine', action='store_true', help='Ép đào khối ngay cả khi cuộc bầu cử chưa kết thúc.') 
        parser.add_argument('--no-export', action='store_true')
        parser.add_argument('--force-restore', action='store_true')

    def _mine_block_for_ballot(self, ballot, options):
        # ... (Hàm này không cần thay đổi nhiều)
        pending_votes = Vote.objects.filter(ballot=ballot, block__isnull=True).order_by('timestamp')
        num_pending_votes = pending_votes.count()

        # if num_pending_votes == 0:
        #     self.stdout.write(f"   Cuộc Bầu Cử '{ballot.title}': Không có phiếu chờ để xử lý.")
        #     return

        self.stdout.write(f"   Đang tiến hành đào khối cuối cùng cho '{ballot.title}' với {num_pending_votes} phiếu chờ...")
        
        last_block = Block.objects.filter(ballot=ballot).order_by('-id').first()
        try:
            with transaction.atomic():
                # Vì chỉ có 1 lần đào, bạn có thể gom tất cả phiếu vào 1 block duy nhất
                # Hoặc vẫn giữ logic tạo nhiều block nếu số phiếu quá lớn (tùy chọn)
                new_block = Block.objects.create(
                    ballot=ballot,
                    previous_hash=last_block.hash if last_block else '0',
                    difficulty=2 
                )
                pending_votes.update(block=new_block)
                new_block.mine_block()
                self.stdout.write(self.style.SUCCESS(f"    -> Đã đào và lưu thành công Khối #{new_block.id}."))
                
                if not options['no_export']:
                    success, msg = save_blockchain_to_json_with_integrity_check(ballot.id, base_export_dir=BLOCKCHAIN_EXPORT_DIR_PER_BALLOT)
                    if success:
                        self.stdout.write(self.style.SUCCESS(f"    -> Đã xuất blockchain: {msg}"))
                    else:
                        self.stdout.write(self.style.ERROR(f"    -> Lỗi khi xuất blockchain: {msg}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   Lỗi khi đào khối cho '{ballot.title}': {e}"))

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Bắt đầu quy trình chốt sổ và đào khối ---'))
        now = timezone.now()

        # Xác định các cuộc bầu cử cần xử lý
        if options['ballot_id']:
            ballots_to_process = Ballot.objects.filter(id=options['ballot_id'])
        else:
            # Chỉ lấy những cuộc bầu cử đã kết thúc hoặc được ép đào
            ballots_to_process = Ballot.objects.all()

        for ballot in ballots_to_process:
            self.stdout.write(f"\n>> Đang xử lý cuộc bầu cử: '{ballot.title}' (ID: {ballot.id})")
            
            is_ended = ballot.end_date < now
            should_mine = False

            # --- LOGIC ĐÀO KHỐI MỚI, ĐƠN GIẢN HÓA ---
            # Chỉ đào khi cuộc bầu cử đã kết thúc HOẶC khi admin ép đào
            if options['force_mine']:
                should_mine = True
                self.stdout.write("   Cờ --force-mine được bật, tiến hành đào.")
            elif is_ended:
                should_mine = True
                self.stdout.write("   Cuộc bầu cử đã kết thúc, tiến hành đào.")
            else:
                self.stdout.write("   Cuộc bầu cử vẫn đang diễn ra, bỏ qua.")
                continue # Bỏ qua và chuyển sang cuộc bầu cử tiếp theo
            
            # # Kiểm tra xem có phiếu chờ không
            # if not Vote.objects.filter(ballot=ballot, block__isnull=True).exists():
            #     self.stdout.write("   Không có phiếu chờ, không cần đào.")
            #     continue

            # --- BƯỚC KIỂM TRA FILE VÀ PHỤC HỒI VẪN GIỮ NGUYÊN ---
            file_path = get_blockchain_file_path(ballot.id, BLOCKCHAIN_EXPORT_DIR_PER_BALLOT)
            if os.path.exists(file_path):
                if not options['force_restore']:
                    is_valid, verify_msg = verify_blockchain_integrity(ballot.id, BLOCKCHAIN_EXPORT_DIR_PER_BALLOT)
                    if not is_valid:
                        self.stdout.write(self.style.ERROR(f"   DỪNG LẠI: {verify_msg}"))
                        continue 
            
            # --- THỰC HIỆN ĐÀO KHỐI ---
            if should_mine:
                self._mine_block_for_ballot(ballot, options)

        self.stdout.write(self.style.SUCCESS('\n--- Quy trình đã hoàn tất ---'))