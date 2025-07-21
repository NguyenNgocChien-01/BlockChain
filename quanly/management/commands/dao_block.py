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
        parser.add_argument(
            '--no-export',
            action='store_true',
            help='Chỉ đào block, không xuất file JSON riêng cho cuộc bầu cử đó.',
        )

    def _mine_final_block_for_ballot(self, ballot, options):
        """
        Hàm riêng để đào khối cuối cùng cho một cuộc bầu cử.
        Hàm này sẽ được gọi cho các cuộc bầu cử đã kết thúc hoặc khi có cờ --force-mine.
        """
        pending_votes = Vote.objects.filter(ballot=ballot, block__isnull=True).order_by('timestamp')
        num_pending_votes = pending_votes.count()

        if num_pending_votes == 0:
            self.stdout.write(f"   Cuộc Bầu Cử '{ballot.title}': Không có phiếu chờ để dọn dẹp.")
            return

        self.stdout.write(self.style.WARNING(f"   Cuộc Bầu Cử '{ballot.title}': Đang thực hiện đào khối cuối cùng với {num_pending_votes} phiếu bầu còn lại..."))
        
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
                
                self.stdout.write(self.style.SUCCESS(f"    -> Đã đào và lưu thành công Khối cuối cùng #{new_block.id}."))
                
                if not options['no_export']:
                    success, msg = save_blockchain_to_json_with_integrity_check(ballot.id, base_export_dir=BLOCKCHAIN_EXPORT_DIR_PER_BALLOT)
                    if success:
                        self.stdout.write(self.style.SUCCESS(f"    -> Đã xuất blockchain riêng: {msg}"))
                    else:
                        self.stdout.write(self.style.ERROR(f"    -> Lỗi khi xuất blockchain riêng: {msg}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   Lỗi khi đào khối cuối cùng cho Cuộc Bầu Cử '{ballot.title}': {e}"))

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Bắt đầu quá trình đào khối và xuất dữ liệu blockchain...'))
        

        
        now = timezone.now()
        # Tìm các cuộc bầu cử đã qua ngày kết thúc và có phiếu đang chờ
        ended_ballots_with_pending_votes = Ballot.objects.annotate(
            has_pending_votes=Exists(Vote.objects.filter(ballot=OuterRef('pk'), block__isnull=True))
        ).filter(end_date__lt=now, has_pending_votes=True).distinct()

        if ended_ballots_with_pending_votes.exists():
            for ballot in ended_ballots_with_pending_votes:
                self._mine_final_block_for_ballot(ballot, options)

        
        processed_ballot_ids = list(ended_ballots_with_pending_votes.values_list('id', flat=True))



        # Lọc theo ballot_id nếu được cung cấp
        if options['ballot_id']:
            ballots_to_process = Ballot.objects.filter(id=options['ballot_id'])
            # Bỏ qua các ballot đã được xử lý ở bước dọn dẹp
            ballots_to_process = ballots_to_process.exclude(id__in=processed_ballot_ids)
        else:
            # Lấy tất cả các cuộc bầu cử đang hoạt động và có phiếu chờ
            ballots_to_process = Ballot.objects.annotate(
                has_pending_votes=Exists(Vote.objects.filter(ballot=OuterRef('pk'), block__isnull=True))
            ).filter(
                end_date__gte=now, # Chỉ xử lý các cuộc bầu cử chưa kết thúc
                has_pending_votes=True
            ).exclude(id__in=processed_ballot_ids).distinct() # Loại trừ các ballot đã xử lý

        if not ballots_to_process.exists():
            self.stdout.write("Không tìm thấy cuộc bầu cử nào đang hoạt động có phiếu chờ để xử lý.")
        else:
            for ballot in ballots_to_process:
                pending_votes = Vote.objects.filter(ballot=ballot, block__isnull=True).order_by('timestamp')
                num_pending_votes = pending_votes.count()
                last_block = Block.objects.filter(ballot=ballot).order_by('-id').first()
                
                should_mine_new_block = False
                
                if options['force_mine'] and num_pending_votes > 0:
                    should_mine_new_block = True
                    self.stdout.write(self.style.WARNING(f"   Cuộc Bầu Cử '{ballot.title}': Cờ --force-mine được bật. Đào block mới..."))
                elif not last_block and num_pending_votes > 0:
                    should_mine_new_block = True
                    self.stdout.write(f"   Cuộc Bầu Cử '{ballot.title}': Cần tạo khối Genesis với {num_pending_votes} phiếu chờ.")
                elif num_pending_votes >= self.MIN_VOTES_PER_BLOCK:
                    should_mine_new_block = True
                    self.stdout.write(f"   Cuộc Bầu Cử '{ballot.title}': Đạt số phiếu tối thiểu ({num_pending_votes}/{self.MIN_VOTES_PER_BLOCK}).")
                elif last_block and num_pending_votes > 0 and (now - last_block.timestamp).total_seconds() >= self.MAX_BLOCK_INTERVAL_SECONDS:
                    should_mine_new_block = True
                    time_since_last_block_min = (now - last_block.timestamp).total_seconds() / 60
                    self.stdout.write(f"   Cuộc Bầu Cử '{ballot.title}': Vượt quá thời gian tối đa ({time_since_last_block_min:.2f} phút).")
                else:
                    self.stdout.write(f"   Cuộc Bầu Cử '{ballot.title}': Không đủ điều kiện đào (số phiếu chờ: {num_pending_votes}).")
                    continue

                if should_mine_new_block:
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
                                    self.stdout.write(self.style.SUCCESS(f"    -> Đã xuất blockchain riêng: {msg}"))
                                else:
                                    self.stdout.write(self.style.ERROR(f"    -> Lỗi khi xuất blockchain riêng: {msg}"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"   Lỗi khi đào khối cho Cuộc Bầu Cử '{ballot.title}': {e}"))
                        continue

        self.stdout.write(self.style.SUCCESS('\nQuá trình đào khối và xuất dữ liệu blockchain đã hoàn tất.'))