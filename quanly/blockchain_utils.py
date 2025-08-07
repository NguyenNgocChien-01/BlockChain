import hashlib
import json
import os
from django.conf import settings
from django.utils import timezone
import unicodedata 
import difflib
import re
import shutil
from .models import *


def get_blockchain_file_path(ballot_id: int, base_export_dir: str) -> str:
    """Trả về đường dẫn tới file JSON blockchain chính."""
    os.makedirs(base_export_dir, exist_ok=True)
    try:
        ballot_obj = Ballot.objects.get(id=ballot_id)
    except Ballot.DoesNotExist:
        return os.path.join(base_export_dir, f"blockchain_unknown_ballot_{ballot_id}.json")

    normalized_title = unicodedata.normalize('NFD', ballot_obj.title)
    ascii_only_title = normalized_title.encode('ascii', 'ignore').decode('utf-8')
    safe_title = re.sub(r'[\s\W]+', '_', ascii_only_title).lower()
    
    file_name = f"blockchain_{safe_title}_{ballot_id}.json"
    return os.path.join(base_export_dir, file_name)

def save_blockchain_to_json(ballot, blocks_data_list: list, base_export_dir: str) -> tuple[bool, str]:
    """
    Hàm mới: Lưu một danh sách các khối (dictionaries) ra file JSON.
    Hàm này không còn truy vấn CSDL.
    """
    blockchain_file_path = get_blockchain_file_path(ballot.id, base_export_dir)
    try:
        # 1. Tính toán chain_hash từ dữ liệu được truyền vào
        full_blocks_json_string = json.dumps(blocks_data_list, indent=4, ensure_ascii=False, sort_keys=True)
        chain_hash = hashlib.sha256(full_blocks_json_string.encode('utf-8')).hexdigest()

        # 2. Tạo cấu trúc dữ liệu xuất cuối cùng
        full_export_data = {
            "ballot_id": ballot.id,
            "ballot_title": ballot.title,
            "exported_at": timezone.now().isoformat(),
            "chain_hash": chain_hash, 
            "blocks": blocks_data_list
        }

        # 3. Ghi toàn bộ dữ liệu vào file JSON
        with open(blockchain_file_path, 'w', encoding='utf-8') as f:
            json.dump(full_export_data, f, indent=4, ensure_ascii=False)
        
        return True, f"Đã lưu thành công file: {os.path.basename(blockchain_file_path)}"
    except Exception as e:
        return False, f"Lỗi khi lưu file JSON: {e}"

def verify_blockchain_integrity(ballot_id: int, base_export_dir: str) -> tuple[bool, str]:
    """
    Kiểm tra tính toàn vẹn của file blockchain JSON.
    Hàm này không cần thay đổi vì nó vốn đã làm việc với file.
    """
    blockchain_file_path = get_blockchain_file_path(ballot_id, base_export_dir)
    if not os.path.exists(blockchain_file_path):
        return True, "File blockchain chưa tồn tại, không cần kiểm tra."

    try:
        with open(blockchain_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if "blocks" not in data or "chain_hash" not in data:
            return False, "File blockchain bị hỏng cấu trúc."

        stored_hash = data["chain_hash"]
        blocks_data = data["blocks"]
        
        recalculated_json_string = json.dumps(blocks_data, indent=4, ensure_ascii=False, sort_keys=True)
        current_hash = hashlib.sha256(recalculated_json_string.encode('utf-8')).hexdigest()

        if stored_hash == current_hash:
            return True, "Blockchain đảm bảo tính toàn vẹn."
        else:
            return False, "Blockchain đã bị sửa đổi! Chain_hash không khớp."
    except Exception as e:
        return False, f"Lỗi khi xác minh file: {e}"


def get_backup_file_path(ballot_id: int, base_export_dir: str) -> str:
    """Trả về đường dẫn đến file backup trong thư mục con 'backups'."""
    original_path = get_blockchain_file_path(ballot_id, base_export_dir)
    backup_dir = os.path.join(base_export_dir, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    return os.path.join(backup_dir, os.path.basename(original_path))

def create_backup(ballot_id: int, base_export_dir: str):
    """Tạo một bản sao lưu của file blockchain chính vào thư mục 'backups'."""
    original_path = get_blockchain_file_path(ballot_id, base_export_dir)
    backup_path = get_backup_file_path(ballot_id, base_export_dir)
    if os.path.exists(original_path):
        shutil.copy2(original_path, backup_path)
        print(f"Đã tạo/cập nhật backup tại: {backup_path}")

def restore_from_backup(ballot_id: int, base_export_dir: str) -> bool:
    """Phục hồi file blockchain chính từ bản sao lưu trong thư mục 'backups'."""
    original_path = get_blockchain_file_path(ballot_id, base_export_dir)
    backup_path = get_backup_file_path(ballot_id, base_export_dir)
    if os.path.exists(backup_path):
        shutil.copy2(backup_path, original_path)
        print(f"Đã phục hồi file '{os.path.basename(original_path)}' từ backup.")
        return True
    return False

def backup_tampered_file(ballot_id: int, base_export_dir: str) -> str:
    """Tạo bản sao lưu của file bị thay đổi vào thư mục 'tampered_backups'."""
    original_path = get_blockchain_file_path(ballot_id, base_export_dir)
    if not os.path.exists(original_path): return None

    backup_dir = os.path.join(base_export_dir, 'tampered_backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = timezone.localtime(timezone.now()).strftime("%Y%m%d_%H%M%S")
    base, ext = os.path.splitext(os.path.basename(original_path))
    
    backup_filename = f"{base}_tampered_{timestamp}{ext}"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    shutil.copy2(original_path, backup_path)
    print(f"Đã tạo backup cho file bị thay đổi tại: {backup_path}")
    return backup_path

# ==============================================================================
# === 3. HÀM GHI LOG VÀ SO SÁNH ===
# ==============================================================================

def compare_files_and_get_diff(original_file_path, tampered_file_path):
    """So sánh hai file và trả về sự khác biệt dưới dạng văn bản."""
    if not os.path.exists(original_file_path) or not os.path.exists(tampered_file_path):
        return "Không thể so sánh do một trong các file không tồn tại."
    try:
        with open(original_file_path, 'r', encoding='utf-8') as f1: original_lines = f1.readlines()
        with open(tampered_file_path, 'r', encoding='utf-8') as f2: tampered_lines = f2.readlines()

        diff = difflib.unified_diff(
            original_lines, tampered_lines,
            fromfile="file_backup_an_toan.json", tofile="file_da_bi_sua_doi.json", lineterm=''
        )
        diff_output = list(diff)
        return '\n'.join(diff_output) if diff_output else "Không tìm thấy sự khác biệt."
    except Exception as e:
        return f"Lỗi khi so sánh file: {e}"

def log_tampering_event(ballot, verify_msg, user, ip_address, backup_path=None):
    """
    Ghi lại sự kiện phát hiện file bị thay đổi vào CSDL.
    ĐÃ CẬP NHẬT: Tự động phân tích và tạo mô tả chi tiết.
    """
    try:
        user_agent_info = getattr(user, 'user_agent', None)
        browser_info = f"{user_agent_info.browser.family} {user_agent_info.browser.version_string}" if user_agent_info else "Không rõ"
        os_info = f"{user_agent_info.os.family} {user_agent_info.os.version_string}" if user_agent_info else "Không rõ"
        
        # --- LOGIC MỚI: TẠO MÔ TẢ CHI TIẾT TỪ KẾT QUẢ SO SÁNH ---
        description_detail = f"Phát hiện file blockchain của '{ballot.title}' bị thay đổi. Hệ thống đã tự động phục hồi." # Mô tả mặc định
        diff_details = ""
        
        if backup_path:
            base_export_dir = os.path.dirname(os.path.dirname(backup_path))
            good_backup_path = get_backup_file_path(ballot.id, base_export_dir)
            
            if os.path.exists(good_backup_path):
                diff_details = compare_files_and_get_diff(good_backup_path, backup_path)
                try:
                    # Phân tích kết quả so sánh để tạo mô tả
                    diff_lines = diff_details.split('\n')
                    first_old_line, first_new_line = None, None
                    for line in diff_lines:
                        if line.startswith('---') or line.startswith('+++') or line.startswith('@@'): continue
                        if line.startswith('-') and first_old_line is None: first_old_line = line[1:].strip()
                        if line.startswith('+') and first_new_line is None: first_new_line = line[1:].strip()
                        if first_old_line and first_new_line: break
                    
                    if first_old_line and first_new_line:
                        old_preview = (first_old_line[:70] + '...') if len(first_old_line) > 70 else first_old_line
                        new_preview = (first_new_line[:70] + '...') if len(first_new_line) > 70 else first_new_line
                        description_detail = f"Phát hiện thay đổi: Nội dung '{old_preview}' đã bị thay đổi thành '{new_preview}'."
                except Exception:
                    pass # Nếu có lỗi phân tích, dùng mô tả mặc định
            else:
                diff_details = "Không thể so sánh: File backup an toàn chưa tồn tại để đối chiếu."
        
        UserTamperLog.objects.create(
            description=description_detail, # <-- SỬ DỤNG MÔ TẢ MỚI
            attempted_by=user if user.is_authenticated else None,
            ip_address=ip_address,
            ballot=ballot,
            details={
                'error_message': verify_msg,
                'browser': browser_info,
                'os': os_info,
                'tamper_diff': diff_details 
            },
            backup_file_path=backup_path
        )
        print(f"Đã ghi cảnh báo an ninh cho cuộc bầu cử ID {ballot.id} vào CSDL.")
    except Exception as e:
        print(f"LỖI NGHIÊM TRỌNG: Không thể ghi log an ninh vào CSDL. Lỗi: {e}")
