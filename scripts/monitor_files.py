# scripts/monitor_files.py
import time
import os
import django
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- Thiết lập môi trường Django ---
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'BauCuProject.settings')
django.setup()
# ------------------------------------

# Import các hàm và model cần thiết từ project của bạn
from django.conf import settings
from quanly.models import Ballot
from quanly.blockchain_utils import (
    verify_blockchain_integrity,
    backup_tampered_file,
    restore_from_backup,
    log_tampering_event,
    get_decrypted_results_path,
    verify_decrypted_results_integrity,
    backup_tampered_file_for_results,
    restore_from_backup_for_results
)

# Định nghĩa các đường dẫn cần theo dõi
BLOCKCHAIN_DIR = os.path.join(settings.BASE_DIR, 'quanly', 'save_blockchain')
RESULTS_DIR = os.path.join(settings.BASE_DIR, 'quanly', 'save_blockchain_result')

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self):
        # Dùng dictionary để lưu lại thời gian xử lý cuối cùng của mỗi file
        self.last_processed = {}
        self.debounce_interval = 2  # Giây

    def on_modified(self, event):
        if event.is_directory:
            return

        filepath = event.src_path
        filename = os.path.basename(filepath)
        
        if "_tampered_" in filename:
            return

        # --- LOGIC MỚI: Chống xử lý lặp lại (Debouncing) ---
        current_time = time.time()
        last_time = self.last_processed.get(filepath, 0)

        if (current_time - last_time) < self.debounce_interval:
            # Nếu sự kiện xảy ra quá nhanh, bỏ qua nó
            return
        
        # Cập nhật lại thời gian xử lý
        self.last_processed[filepath] = current_time
        # --- KẾT THÚC LOGIC MỚI ---

        print(f"\n[PHÁT HIỆN THAY ĐỔI] File: {filename}")

        # Sử dụng regex mạnh mẽ hơn để trích xuất ballot_id
        match = re.search(r'blockchain_.+?_(\d+)', filename)
        if not match:
            return
        
        ballot_id = int(match.group(1))
        try:
            ballot = Ballot.objects.get(pk=ballot_id)
        except Ballot.DoesNotExist:
            return

        # Kiểm tra xem đây là file blockchain gốc hay file kết quả
        if "decrypted_results" in filename:
            is_valid, msg = verify_decrypted_results_integrity(ballot_id, RESULTS_DIR)
            if not is_valid:
                print(f"� CẢNH BÁO: Phát hiện hành vi sửa đổi file kết quả '{filename}'. Thông tin đã được ghi lại.")
                backup_path = backup_tampered_file_for_results(ballot_id, RESULTS_DIR)
                log_tampering_event(
                    ballot=ballot,
                    verify_msg=f"FILE KẾT QUẢ: {msg}",
                    user=None,
                    ip_address="127.0.0.1 (System Monitor)",
                    backup_path=backup_path,
                    file_type='results'
                )
                if restore_from_backup_for_results(ballot_id, RESULTS_DIR):
                    print("✅ Hệ thống đã tự động phục hồi file từ bản sao lưu an toàn.")
                else:
                    print("❌ LỖI NGHIÊM TRỌNG: Không thể phục hồi file kết quả!")
        else:
            is_valid, msg = verify_blockchain_integrity(ballot_id, BLOCKCHAIN_DIR)
            if not is_valid:
                print(f"🚨 CẢNH BÁO: Phát hiện hành vi sửa đổi file blockchain '{filename}'. Thông tin đã được ghi lại.")
                backup_path = backup_tampered_file(ballot_id, BLOCKCHAIN_DIR)
                log_tampering_event(
                    ballot=ballot,
                    verify_msg=f"FILE BLOCKCHAIN: {msg}",
                    user=None,
                    ip_address="127.0.0.1 (System Monitor)",
                    backup_path=backup_path,
                    file_type='blockchain'
                )
                if restore_from_backup(ballot_id, BLOCKCHAIN_DIR):
                    print("✅ Hệ thống đã tự động phục hồi file từ bản sao lưu an toàn.")
                else:
                    print("❌ LỖI NGHIÊM TRỌNG: Không thể phục hồi file blockchain!")

def run():
    """Hàm chính để chạy script."""
    event_handler = FileChangeHandler()
    observer = Observer()
    
    os.makedirs(BLOCKCHAIN_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    observer.schedule(event_handler, BLOCKCHAIN_DIR, recursive=True)
    observer.schedule(event_handler, RESULTS_DIR, recursive=True)
    
    observer.start()
    print(f"🚀 Bắt đầu giám sát các thư mục an ninh...")
    print(f" - Thư mục Blockchain: {os.path.abspath(BLOCKCHAIN_DIR)}")
    print(f" - Thư mục Kết quả: {os.path.abspath(RESULTS_DIR)}")
    print("Nhấn Ctrl+C để dừng.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
