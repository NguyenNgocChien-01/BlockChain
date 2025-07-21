# quanly/management/commands/mine_and_export.py

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
    help = 'Kiểm tra file blockchain hiện tại, sau đó đào khối mới và xuất file.'
    
    MIN_VOTES_PER_BLOCK = 1 
    MAX_BLOCK_INTERVAL_SECONDS = 300 

    def add_arguments(self, parser):
        parser.add_argument('--ballot-id', type=int)
        parser.add_argument('--force-mine', action='store_true')
        parser.add_argument('--no-export', action='store_true')
        parser.add_argument(
            '--force-restore',
            action='store_true',
            help='Bỏ qua cảnh báo toàn vẹn và ghi đè file JSON bằng dữ liệu mới từ database.'
        )

        

    def _mine_block_for_ballot(self, ballot, options, is_final=False):
        pending_votes = Vote.objects.filter(ballot=ballot, block__isnull=True).order_by('timestamp')
        num_pending_votes = pending_votes.count()

        if num_pending_votes == 0:
            if is_final:
                self.stdout.write(f"   Cuộc Bầu Cử '{ballot.title}': Không có phiếu chờ để dọn dẹp.")
            return

        last_block = Block.objects.filter(ballot=ballot).order_by('-id').first()
        try:
            with transaction.atomic():
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
        self.stdout.write(self.style.SUCCESS('--- Bắt đầu quy trình ---'))
        now = timezone.now()

        # Xác định các cuộc bầu cử cần xử lý
        if options['ballot_id']:
            ballots_to_process = Ballot.objects.filter(id=options['ballot_id'])
        else:
            ballots_to_process = Ballot.objects.all()
        for ballot in ballots_to_process:
            self.stdout.write(f"\n>> Đang xử lý cuộc bầu cử: '{ballot.title}' (ID: {ballot.id})")
            
            file_path = get_blockchain_file_path(ballot.id, BLOCKCHAIN_EXPORT_DIR_PER_BALLOT)
            if os.path.exists(file_path):
  
                if not options['force_restore']: # Chỉ kiểm tra nếu KHÔNG có cờ phục hồi
                    self.stdout.write("   Kiểm tra file blockchain hiện có...")
                    is_valid, verify_msg = verify_blockchain_integrity(ballot.id, BLOCKCHAIN_EXPORT_DIR_PER_BALLOT)
                    if not is_valid:
                        self.stdout.write(self.style.ERROR(f"    DỪNG LẠI: {verify_msg}"))
                        self.stdout.write(self.style.WARNING(f"   Gợi ý: Dùng cờ --force-restore để ghi đè file này bằng dữ liệu từ database."))
                        continue 
                    else:
                        self.stdout.write(self.style.SUCCESS("    File hiện tại toàn vẹn."))
                else:
                    self.stdout.write(self.style.WARNING("   Bỏ qua kiểm tra toàn vẹn do có cờ --force-restore."))
            

            pending_votes_count = Vote.objects.filter(ballot=ballot, block__isnull=True).count()
            last_block = Block.objects.filter(ballot=ballot).order_by('-id').first()
            is_ended = ballot.end_date < now
            should_mine = False

            if pending_votes_count == 0:
                self.stdout.write("   Không có phiếu chờ, bỏ qua việc đào.")
                continue

            if options['force_mine']:
                should_mine = True
                self.stdout.write("   Cờ --force-mine được bật, tiến hành đào.")
            elif is_ended:
                should_mine = True
                self.stdout.write("   Cuộc bầu cử đã kết thúc, tiến hành đào khối cuối cùng.")
            elif not last_block:
                should_mine = True
                self.stdout.write("   Chưa có khối nào, tiến hành đào khối Genesis.")
            elif pending_votes_count >= self.MIN_VOTES_PER_BLOCK:
                should_mine = True
                self.stdout.write(f"   Đạt số phiếu tối thiểu ({pending_votes_count}/{self.MIN_VOTES_PER_BLOCK}), tiến hành đào.")
            elif (now - last_block.timestamp).total_seconds() >= self.MAX_BLOCK_INTERVAL_SECONDS:
                should_mine = True
                self.stdout.write("   Vượt quá thời gian chờ tối đa, tiến hành đào.")
            

            if should_mine:
                self._mine_block_for_ballot(ballot, options, is_final=is_ended)
            else:
                self.stdout.write("   Chưa đủ điều kiện đào khối mới.")

        self.stdout.write(self.style.SUCCESS('\n--- Quy trình đã hoàn tất ---'))