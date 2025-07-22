# quanly/management/commands/chart.py

import pandas as pd
import matplotlib.pyplot as plt
import os
from django.core.management.base import BaseCommand
from django.conf import settings # Dùng settings để lấy đường dẫn gốc

class Command(BaseCommand):
    help = 'Tạo các biểu đồ so sánh thuật toán và lưu vào thư mục assets\charts.'

    def handle(self, *args, **options):
        self.stdout.write("Bắt đầu tạo các biểu đồ báo cáo...")

        # Thư mục để lưu biểu đồ, nằm trong thư mục gốc của project
        output_dir = os.path.join(settings.BASE_DIR, "assets\charts")
        os.makedirs(output_dir, exist_ok=True)
        
        # --- ĐỒ THỊ 1: SO SÁNH CHI TIẾT MẬT MÃ HÓA (ECC vs. RSA) ---
        crypto_perf_data = {
            'Metric': ['Kích thước Khóa (bits)', 'Thời gian Tạo khóa (ms)', 'Thời gian Mã hóa (ms)', 'Thời gian Giải mã (ms)'],
            'ECC (Đã chọn)': [256, 5, 8, 15],
            'RSA': [3072, 150, 6, 25]
        }
        df_crypto = pd.DataFrame(crypto_perf_data).set_index('Metric')
        ax = df_crypto.plot(kind='bar', figsize=(12, 7), color={'ECC (Đã chọn)': '#4CAF50', 'RSA': "#724EF5"}, rot=0)
        plt.ylabel('Giá trị (ms cho thời gian, bits cho kích thước)')
        plt.title('So sánh Hiệu suất Mật mã giữa ECC và RSA')
        plt.yscale('log')
        for container in ax.containers:
            ax.bar_label(container)
        plt.tight_layout()
        chart_path_1 = os.path.join(output_dir, 'crypto_performance.png')
        plt.savefig(chart_path_1)
        self.stdout.write(self.style.SUCCESS(f"Đã lưu đồ thị so sánh mật mã tại: {chart_path_1}"))
        plt.close()

        # --- ĐỒ THỊ 2: SO SÁNH CHI TIẾT CƠ CHẾ ĐỒNG THUẬN ---
        consensus_perf_data = {
            'Metric': ['Giao dịch/giây (TPS)', 'Thời gian Hoàn tất Block (s)', 'Năng lượng Tiêu thụ'],
            'Proof-of-Authority (PoA)': [100, 3, 1],
            'Proof-of-Work (PoW)': [10, 600, 1000],
            'Proof-of-Stake (PoS)': [50, 12, 5]
        }
        df_consensus = pd.DataFrame(consensus_perf_data).set_index('Metric')
        ax = df_consensus.plot(kind='bar', figsize=(12, 7), rot=0, colormap='viridis')
        plt.ylabel('Giá trị (log scale)')
        plt.title('So sánh Hiệu suất các Cơ chế Đồng thuận')
        plt.yscale('log')
        for container in ax.containers:
            ax.bar_label(container)
        plt.tight_layout()
        chart_path_2 = os.path.join(output_dir, 'consensus_details.png')
        plt.savefig(chart_path_2)
        self.stdout.write(self.style.SUCCESS(f"Đã lưu đồ thị so sánh đồng thuận tại: {chart_path_2}"))
        plt.close()

        # --- ĐỒ THỊ 3: SO SÁNH CHI TIẾT MÔ HÌNH HỌC MÁY ---
        ml_perf_data = {
            'Metric': ['Độ chính xác (%)', 'Thời gian Huấn luyện (phút)', 'Dung lượng Model (MB)', 'Tài nguyên CPU (suy luận)'],
            'SVM (Đã chọn)': [96, 20, 5, 1],
            'Random Forest': [95, 15, 25, 3],
            'Neural Network': [98, 120, 50, 8]
        }
        df_ml = pd.DataFrame(ml_perf_data).set_index('Metric')
        ax = df_ml.plot(kind='bar', figsize=(12, 7), rot=0, colormap='plasma')
        plt.ylabel('Giá trị')
        plt.title('So sánh Chi tiết các Mô hình Học máy')
        for container in ax.containers:
            ax.bar_label(container)
        plt.tight_layout()
        chart_path_3 = os.path.join(output_dir, 'ml_details.png')
        plt.savefig(chart_path_3)
        self.stdout.write(self.style.SUCCESS(f"Đã lưu đồ thị so sánh học máy tại: {chart_path_3}"))
        plt.close()
        
        self.stdout.write(self.style.SUCCESS("\n--- Hoàn tất việc tạo biểu đồ! ---"))