import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
from django.core.management.base import BaseCommand
from django.conf import settings 
# Import các models cần thiết và TruncDate
from quanly.models import Ballot, Block, Vote 
from django.db.models import Count
from django.db.models.functions import TruncDate
from matplotlib.ticker import MaxNLocator # Thêm import này

class Command(BaseCommand):
    help = 'Tạo các biểu đồ so sánh thuật toán và phân tích dữ liệu từ database.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Bắt đầu tạo các biểu đồ báo cáo...'))

        output_dir = os.path.join(settings.BASE_DIR, "assets", "charts")
        os.makedirs(output_dir, exist_ok=True)
        
        # --- CÁC BIỂU ĐỒ LÝ THUYẾT (GIỮ NGUYÊN) ---
        self.stdout.write("\n--- 1. Tạo đồ thị So sánh Hiệu suất Mật mã ---")
        self._create_crypto_chart(output_dir)

        self.stdout.write("\n--- 2. Tạo đồ thị So sánh Hiệu suất các Cơ chế Đồng thuận ---")
        self._create_consensus_chart(output_dir)

        # --- CÁC BIỂU ĐỒ MỚI TỪ DATABASE ---
        self.stdout.write("\n--- 3. Tạo đồ thị Phân bố Phiếu bầu theo Thời gian ---")
        self._create_votes_over_time_chart(output_dir)

        self.stdout.write("\n--- 4. Tạo đồ thị Số lượng Phiếu bầu trong mỗi Khối ---")
        self._create_votes_per_block_chart(output_dir)

        self.stdout.write(self.style.SUCCESS("\n--- Hoàn tất việc tạo biểu đồ! ---"))

    def _create_crypto_chart(self, output_dir):
        crypto_perf_data = {
            'Metric': ['Kích thước Khóa (bits)', 'Thời gian Tạo khóa (ms)', 'Thời gian Ký (ms)'],
            'ECC (Đã chọn)': [256, 5, 3], 
            'RSA (Phổ biến)': [2048, 150, 10] 
        }
        df_crypto = pd.DataFrame(crypto_perf_data).set_index('Metric')
        ax = df_crypto.plot(kind='bar', figsize=(12, 7), color={'ECC (Đã chọn)': '#4CAF50', 'RSA (Phổ biến)': "#FF9800"}, rot=0) 
        plt.ylabel('Giá trị (log scale)') 
        plt.title('So sánh Hiệu suất Mật mã giữa ECC và RSA')
        plt.yscale('log') 
        for container in ax.containers:
            ax.bar_label(container, fmt='%.0f') 
        plt.tight_layout()
        chart_path = os.path.join(output_dir, '1_crypto_performance.png')
        plt.savefig(chart_path)
        self.stdout.write(self.style.SUCCESS(f"Đã lưu đồ thị tại: {chart_path}"))
        plt.close()

    def _create_consensus_chart(self, output_dir):
        consensus_perf_data = {
            'Metric': ['Giao dịch/giây (TPS)', 'Thời gian Hoàn tất Block (s)', 'Năng lượng Tiêu thụ (Đơn vị)'], 
            'PoA + PoW (Mô hình này)': [50, 5, 10],
            'Public PoW (Bitcoin)': [7, 600, 1000],
            'Public PoS (Ethereum)': [30, 12, 1]
        }
        df_consensus = pd.DataFrame(consensus_perf_data).set_index('Metric')
        ax = df_consensus.plot(kind='bar', figsize=(12, 7), rot=0, colormap='viridis')
        plt.ylabel('Giá trị (log scale)')
        plt.title('So sánh Hiệu suất các Mô hình Blockchain')
        plt.yscale('log')
        for container in ax.containers:
            ax.bar_label(container, fmt='%.0f')
        plt.tight_layout()
        chart_path = os.path.join(output_dir, '2_consensus_details.png')
        plt.savefig(chart_path)
        self.stdout.write(self.style.SUCCESS(f"Đã lưu đồ thị tại: {chart_path}"))
        plt.close()

    def _create_votes_over_time_chart(self, output_dir):
        votes_by_day = Vote.objects.annotate(date=TruncDate('timestamp')).values('date').annotate(count=Count('id')).order_by('date')

        if not votes_by_day:
            self.stdout.write(self.style.WARNING("Không có dữ liệu phiếu bầu để vẽ biểu đồ phân bố theo thời gian."))
            return

        df = pd.DataFrame(list(votes_by_day))
        df['date'] = pd.to_datetime(df['date'])

        plt.figure(figsize=(12, 7))
        ax = plt.gca() # Lấy đối tượng trục hiện tại
        
        # --- THAY ĐỔI TỪ LINE CHART SANG BAR CHART ---
        ax.bar(df['date'], df['count'], color='#007bff', width=0.5)
        # --- KẾT THÚC THAY ĐỔI ---
        
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_ylim(bottom=0)

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m-%Y'))
        ax.xaxis.set_major_locator(mdates.DayLocator())
        plt.gcf().autofmt_xdate()
        plt.title('Phân bố Lượt Bỏ phiếu theo Ngày')
        plt.xlabel('Ngày')
        plt.ylabel('Số lượng Phiếu bầu')
        plt.grid(axis='y', linestyle='--', alpha=0.6) # Chỉ hiện lưới ngang cho dễ đọc
        plt.tight_layout()
        chart_path = os.path.join(output_dir, '3_votes_over_time.png')
        plt.savefig(chart_path)
        self.stdout.write(self.style.SUCCESS(f"Đã lưu đồ thị tại: {chart_path}"))
        plt.close()

    def _create_votes_per_block_chart(self, output_dir):
        votes_in_blocks = Block.objects.annotate(num_votes=Count('votes')).order_by('id')
        votes_in_blocks = [block for block in votes_in_blocks if block.num_votes > 0]

        if not votes_in_blocks:
            self.stdout.write(self.style.WARNING("Chưa có khối nào chứa phiếu bầu để vẽ biểu đồ."))
            return

        block_ids = [f"Khối #{b.id}" for b in votes_in_blocks]
        num_votes = [b.num_votes for b in votes_in_blocks]

        plt.figure(figsize=(12, 7))
        ax = plt.gca() # Lấy đối tượng trục hiện tại
        ax.bar(block_ids, num_votes, color='#28a745')

        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_ylim(bottom=0)

        plt.title('Số lượng Phiếu bầu được Ghi nhận trong mỗi Khối')
        plt.xlabel('Khối')
        plt.ylabel('Số lượng Phiếu bầu')
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        chart_path = os.path.join(output_dir, '4_votes_per_block.png')
        plt.savefig(chart_path)
        self.stdout.write(self.style.SUCCESS(f"Đã lưu đồ thị tại: {chart_path}"))
        plt.close()
