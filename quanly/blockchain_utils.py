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


# def get_blockchain_file_path(ballot_id: int, base_export_dir: str) -> str:
#     """Trả về đường dẫn tới file JSON blockchain chính."""
#     os.makedirs(base_export_dir, exist_ok=True)
#     try:
#         ballot_obj = Ballot.objects.get(id=ballot_id)
#     except Ballot.DoesNotExist:
#         return os.path.join(base_export_dir, f"blockchain_unknown_ballot_{ballot_id}.json")

#     normalized_title = unicodedata.normalize('NFD', ballot_obj.title)
#     ascii_only_title = normalized_title.encode('ascii', 'ignore').decode('utf-8')
#     safe_title = re.sub(r'[\s\W]+', '_', ascii_only_title).lower()
    
#     file_name = f"blockchain_{safe_title}_{ballot_id}.json"
#     return os.path.join(base_export_dir, file_name)

# def save_blockchain_to_json(ballot, blocks_data_list: list, base_export_dir: str) -> tuple[bool, str]:
#     """
#     Hàm mới: Lưu một danh sách các khối (dictionaries) ra file JSON.
#     Hàm này không còn truy vấn CSDL.
#     """
#     blockchain_file_path = get_blockchain_file_path(ballot.id, base_export_dir)
#     try:
#         # 1. Tính toán chain_hash từ dữ liệu được truyền vào
#         full_blocks_json_string = json.dumps(blocks_data_list, indent=4, ensure_ascii=False, sort_keys=True)
#         chain_hash = hashlib.sha256(full_blocks_json_string.encode('utf-8')).hexdigest()

#         # 2. Tạo cấu trúc dữ liệu xuất cuối cùng
#         full_export_data = {
#             "ballot_id": ballot.id,
#             "ballot_title": ballot.title,
#             "exported_at": timezone.now().isoformat(),
#             "chain_hash": chain_hash, 
#             "blocks": blocks_data_list
#         }

#         # 3. Ghi toàn bộ dữ liệu vào file JSON
#         with open(blockchain_file_path, 'w', encoding='utf-8') as f:
#             json.dump(full_export_data, f, indent=4, ensure_ascii=False)
        
#         return True, f"Đã lưu thành công file: {os.path.basename(blockchain_file_path)}"
#     except Exception as e:
#         return False, f"Lỗi khi lưu file JSON: {e}"

# def verify_blockchain_integrity(ballot_id: int, base_export_dir: str) -> tuple[bool, str]:
#     """
#     Kiểm tra tính toàn vẹn của file blockchain JSON.
#     Hàm này không cần thay đổi vì nó vốn đã làm việc với file.
#     """
#     blockchain_file_path = get_blockchain_file_path(ballot_id, base_export_dir)
#     if not os.path.exists(blockchain_file_path):
#         return True, "File blockchain chưa tồn tại, không cần kiểm tra."

#     try:
#         with open(blockchain_file_path, 'r', encoding='utf-8') as f:
#             data = json.load(f)
        
#         if "blocks" not in data or "chain_hash" not in data:
#             return False, "File blockchain bị hỏng cấu trúc."

#         stored_hash = data["chain_hash"]
#         blocks_data = data["blocks"]
        
#         recalculated_json_string = json.dumps(blocks_data, indent=4, ensure_ascii=False, sort_keys=True)
#         current_hash = hashlib.sha256(recalculated_json_string.encode('utf-8')).hexdigest()

#         if stored_hash == current_hash:
#             return True, "Blockchain đảm bảo tính toàn vẹn."
#         else:
#             return False, "Blockchain đã bị sửa đổi! Chain_hash không khớp."
#     except Exception as e:
#         return False, f"Lỗi khi xác minh file: {e}"


# def get_backup_file_path(ballot_id: int, base_export_dir: str) -> str:
#     """Trả về đường dẫn đến file backup trong thư mục con 'backups'."""
#     original_path = get_blockchain_file_path(ballot_id, base_export_dir)
#     backup_dir = os.path.join(base_export_dir, 'backups')
#     os.makedirs(backup_dir, exist_ok=True)
#     return os.path.join(backup_dir, os.path.basename(original_path))

# def create_backup(ballot_id: int, base_export_dir: str):
#     """Tạo một bản sao lưu của file blockchain chính vào thư mục 'backups'."""
#     original_path = get_blockchain_file_path(ballot_id, base_export_dir)
#     backup_path = get_backup_file_path(ballot_id, base_export_dir)
#     if os.path.exists(original_path):
#         shutil.copy2(original_path, backup_path)
#         print(f"Đã tạo/cập nhật backup tại: {backup_path}")

# def restore_from_backup(ballot_id: int, base_export_dir: str) -> bool:
#     """Phục hồi file blockchain chính từ bản sao lưu trong thư mục 'backups'."""
#     original_path = get_blockchain_file_path(ballot_id, base_export_dir)
#     backup_path = get_backup_file_path(ballot_id, base_export_dir)
#     if os.path.exists(backup_path):
#         shutil.copy2(backup_path, original_path)
#         print(f"Đã phục hồi file '{os.path.basename(original_path)}' từ backup.")
#         return True
#     return False

# def restore_from_backup_result(ballot_id: int, export_dir: str) -> tuple[bool, str]:
#     """
#     Phục hồi file sổ cái từ bản sao lưu an toàn gần nhất.
#     Trả về True và thông báo nếu thành công, False và lỗi nếu thất bại.
#     """
#     source_file_path = get_blockchain_file_path(ballot_id, export_dir)
#     backup_dir = os.path.join(export_dir, 'backups')
    
#     # Tìm tất cả các file backup cho cuộc bầu cử này
#     backups = sorted(
#         [f for f in os.listdir(backup_dir) if f.startswith(f"blockchain_{ballot_id}")]
#     , reverse=True)
    
#     if not backups:
#         return False, "Không có bản sao lưu nào để phục hồi."
        
#     last_backup_path = os.path.join(backup_dir, backups[0])
    
#     try:
#         shutil.copyfile(last_backup_path, source_file_path)
#         return True, f"Đã phục hồi file từ bản sao lưu gần nhất: {os.path.basename(last_backup_path)}."
#     except FileNotFoundError:
#         return False, f"Không tìm thấy file backup tại đường dẫn: {last_backup_path}."
#     except Exception as e:
#         return False, f"Lỗi không xác định khi phục hồi: {e}."

# def backup_tampered_file(ballot_id: int, base_export_dir: str) -> str:
#     """Tạo bản sao lưu của file bị thay đổi vào thư mục 'tampered_backups'."""
#     original_path = get_blockchain_file_path(ballot_id, base_export_dir)
#     if not os.path.exists(original_path): return None

#     backup_dir = os.path.join(base_export_dir, 'tampered_backups')
#     os.makedirs(backup_dir, exist_ok=True)
    
#     timestamp = timezone.localtime(timezone.now()).strftime("%Y%m%d_%H%M%S")
#     base, ext = os.path.splitext(os.path.basename(original_path))
    
#     backup_filename = f"{base}_tampered_{timestamp}{ext}"
#     backup_path = os.path.join(backup_dir, backup_filename)
    
#     shutil.copy2(original_path, backup_path)
#     print(f"Đã tạo backup cho file bị thay đổi tại: {backup_path}")
#     return backup_path



# # ==============================================================================
# # === 2. HÀM TIỆN ÍCH MỚI CHO FILE KẾT QUẢ (ĐÃ GIẢI MÃ) ===
# # ==============================================================================




# def get_decrypted_results_path(ballot_id: int, base_export_dir: str) -> str:
#     """Trả về đường dẫn đến file kết quả đã được giải mã."""
#     original_path = get_blockchain_file_path(ballot_id, base_export_dir)
#     base, ext = os.path.splitext(os.path.basename(original_path))
#     decrypted_filename = f"{base}_decrypted_results.json"
#     return os.path.join(base_export_dir, decrypted_filename)

# def save_decrypted_blockchain_to_json(ballot: Ballot, sorted_results: list, base_export_dir: str) -> tuple[bool, str]:
#     """Lưu kết quả đã giải mã ra file JSON, đã được niêm phong bằng 'results_hash'."""
#     filepath = get_decrypted_results_path(ballot.id, base_export_dir)
#     try:
#         results_string = json.dumps(sorted_results, sort_keys=True, ensure_ascii=False)
#         results_hash = hashlib.sha256(results_string.encode('utf-8')).hexdigest()
#         final_results_data = {
#             "ballot_id": ballot.id,
#             "ballot_title": ballot.title,
#             "tally_completed_at": timezone.localtime(timezone.now()).isoformat(),
#             "results_hash": results_hash,
#             "results": sorted_results
#         }
#         with open(filepath, 'w', encoding='utf-8') as f:
#             json.dump(final_results_data, f, indent=4, ensure_ascii=False)
#         return True, f"Đã lưu thành công file kết quả: {os.path.basename(filepath)}"
#     except Exception as e:
#         return False, f"Lỗi khi lưu file kết quả: {e}"

# def create_backup_for_results(ballot_id: int, base_export_dir: str):
#     """Tạo một bản sao lưu an toàn cho file kết quả."""
#     original_path = get_decrypted_results_path(ballot_id, base_export_dir)
#     backup_dir = os.path.join(os.path.dirname(original_path), 'backups')
#     os.makedirs(backup_dir, exist_ok=True)
#     backup_path = os.path.join(backup_dir, os.path.basename(original_path))
#     if os.path.exists(original_path):
#         shutil.copy2(original_path, backup_path)
#         print(f"Đã tạo backup cho file kết quả tại: {backup_path}")


def get_blockchain_file_path(ballot_id: int, base_export_dir: str) -> str:
    """Trả về đường dẫn tới file JSON blockchain chính."""
    os.makedirs(base_export_dir, exist_ok=True)
    try:
        ballot_obj = Ballot.objects.get(id=ballot_id)
        normalized_title = unicodedata.normalize('NFD', ballot_obj.title)
        ascii_only_title = normalized_title.encode('ascii', 'ignore').decode('utf-8')
        safe_title = re.sub(r'[\s\W]+', '_', ascii_only_title).lower()
        file_name = f"blockchain_{safe_title}_{ballot_id}.json"
    except Ballot.DoesNotExist:
        file_name = f"blockchain_unknown_ballot_{ballot_id}.json"
    return os.path.join(base_export_dir, file_name)

def save_blockchain_to_json(ballot, blocks_data_list: list, base_export_dir: str) -> tuple[bool, str]:
    """Lưu một danh sách các khối (dictionaries) ra file JSON."""
    blockchain_file_path = get_blockchain_file_path(ballot.id, base_export_dir)
    try:
        full_blocks_json_string = json.dumps(blocks_data_list, indent=4, ensure_ascii=False, sort_keys=True)
        chain_hash = hashlib.sha256(full_blocks_json_string.encode('utf-8')).hexdigest()
        full_export_data = {
            "ballot_id": ballot.id,
            "ballot_title": ballot.title,
            "exported_at": timezone.now().isoformat(),
            "chain_hash": chain_hash, 
            "blocks": blocks_data_list
        }
        with open(blockchain_file_path, 'w', encoding='utf-8') as f:
            json.dump(full_export_data, f, indent=4, ensure_ascii=False)
        return True, f"Đã lưu thành công file: {os.path.basename(blockchain_file_path)}"
    except Exception as e:
        return False, f"Lỗi khi lưu file JSON: {e}"

def verify_blockchain_integrity(ballot_id: int, base_export_dir: str) -> tuple[bool, str]:
    """Kiểm tra tính toàn vẹn của file blockchain JSON."""
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
# === 2. HÀM TIỆN ÍCH MỚI CHO FILE KẾT QUẢ (ĐÃ GIẢI MÃ) ===
# ==============================================================================
def get_decrypted_results_path(ballot_id: int, base_export_dir: str) -> str:
    """Trả về đường dẫn đến file kết quả đã được giải mã."""
    original_path = get_blockchain_file_path(ballot_id, base_export_dir)
    base, ext = os.path.splitext(os.path.basename(original_path))
    decrypted_filename = f"{base}_decrypted_results.json"
    return os.path.join(base_export_dir, decrypted_filename)

def save_decrypted_blockchain_to_json(ballot, sorted_results, base_export_dir: str) -> tuple[bool, str]:
    """Lưu kết quả đã giải mã ra file JSON, đã được niêm phong bằng 'results_hash'."""
    filepath = get_decrypted_results_path(ballot.id, base_export_dir)
    try:
        results_string = json.dumps(sorted_results, sort_keys=True, ensure_ascii=False)
        results_hash = hashlib.sha256(results_string.encode('utf-8')).hexdigest()

        final_data = {
            "ballot_id": ballot.id,
            "ballot_title": ballot.title,
            "tally_completed_at": timezone.localtime(timezone.now()).isoformat(),
            "results_hash": results_hash, # <-- NIÊM PHONG
            "results": sorted_results
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        return True, f"Đã lưu thành công file kết quả: {os.path.basename(filepath)}"
    except Exception as e:
        return False, f"Lỗi khi lưu file kết quả: {e}"

def verify_decrypted_results_integrity(ballot_id: int, base_export_dir: str) -> tuple[bool, str]:
    """Kiểm tra tính toàn vẹn của file kết quả đã giải mã."""
    filepath = get_decrypted_results_path(ballot_id, base_export_dir)
    if not os.path.exists(filepath):
        return True, "File kết quả chưa tồn tại."
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if "results" not in data or "results_hash" not in data:
            return False, "File kết quả bị hỏng cấu trúc."
        
        stored_hash = data["results_hash"]
        results_data = data["results"]
        recalculated_string = json.dumps(results_data, sort_keys=True, ensure_ascii=False)
        current_hash = hashlib.sha256(recalculated_string.encode('utf-8')).hexdigest()
        
        if stored_hash == current_hash:
            return True, "File kết quả đảm bảo tính toàn vẹn."
        else:
            return False, "File kết quả đã bị sửa đổi! Hash không khớp."
    except Exception as e:
        return False, f"Lỗi khi xác minh file kết quả: {e}"

def get_backup_results_path(ballot_id: int, base_export_dir: str) -> str:
    """Trả về đường dẫn đến file backup cho kết quả đã giải mã."""
    original_path = get_decrypted_results_path(ballot_id, base_export_dir)
    backup_dir = os.path.join(os.path.dirname(original_path), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    return os.path.join(backup_dir, os.path.basename(original_path))

def create_backup_for_results(ballot_id: int, base_export_dir: str):
    """Tạo một bản sao lưu an toàn cho file kết quả."""
    original_path = get_decrypted_results_path(ballot_id, base_export_dir)
    backup_path = get_backup_results_path(ballot_id, base_export_dir)
    if os.path.exists(original_path):
        shutil.copy2(original_path, backup_path)
        print(f"Đã tạo backup cho file kết quả tại: {backup_path}")

def restore_from_backup_for_results(ballot_id: int, base_export_dir: str) -> bool:
    """Phục hồi file kết quả từ bản sao lưu an toàn."""
    original_path = get_decrypted_results_path(ballot_id, base_export_dir)
    backup_path = get_backup_results_path(ballot_id, base_export_dir)
    if os.path.exists(backup_path):
        shutil.copy2(backup_path, original_path)
        print(f"Đã phục hồi file kết quả từ backup.")
        return True
    return False

def backup_tampered_file_for_results(ballot_id: int, base_export_dir: str) -> str:
    """Tạo bản sao lưu bằng chứng cho file kết quả đã bị thay đổi."""
    original_path = get_decrypted_results_path(ballot_id, base_export_dir)
    if not os.path.exists(original_path): return None
    
    backup_dir = os.path.join(os.path.dirname(original_path), 'tampered_backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = timezone.localtime(timezone.now()).strftime("%Y%m%d_%H%M%S")
    base, ext = os.path.splitext(os.path.basename(original_path))
    backup_filename = f"{base}_tampered_{timestamp}{ext}"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    shutil.copy2(original_path, backup_path)
    # print(f"Đã tạo backup bằng chứng cho file kết quả tại: {backup_path}")
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

def compare_results_and_get_diff_summary(original_file_path, tampered_file_path):
    """
    Hàm mới: So sánh hai file kết quả và tạo ra một mô tả có ý nghĩa.
    """
    try:
        with open(original_file_path, 'r', encoding='utf-8') as f1:
            original_data = json.load(f1).get('results', [])
        with open(tampered_file_path, 'r', encoding='utf-8') as f2:
            tampered_data = json.load(f2).get('results', [])

        original_map = {item['name'].strip(): item['count'] for item in original_data}
        tampered_map = {item['name'].strip(): item['count'] for item in tampered_data}
        
        all_names = set(original_map.keys()) | set(tampered_map.keys())
        changes = []

        for name in all_names:
            original_count = original_map.get(name)
            tampered_count = tampered_map.get(name)
            if original_count != tampered_count:
                if original_count is None:
                    changes.append(f"ứng viên '{name}' được thêm vào với {tampered_count} phiếu")
                elif tampered_count is None:
                    changes.append(f"ứng viên '{name}' (có {original_count} phiếu) đã bị xóa")
                else:
                    changes.append(f"số phiếu của ứng viên '{name}' bị thay đổi từ {original_count} thành {tampered_count}")
        
        return "; ".join(changes) if changes else "Không có thay đổi về số phiếu."

    except Exception as e:
        return f"Không thể phân tích chi tiết sự thay đổi: {e}"

def log_tampering_event(ballot, verify_msg, user, ip_address, backup_path=None, file_type='blockchain'):
    """
    Ghi lại sự kiện phát hiện file bị thay đổi vào CSDL.
    ĐÃ CẬP NHẬT: Thêm tham số 'file_type' để tìm đúng file backup.
    """
    try:
       
        # Chỉ lấy thông tin trình duyệt nếu có đối tượng user
        if user and hasattr(user, 'user_agent'):
            user_agent_info = user.user_agent
            browser_info = f"{user_agent_info.browser.family} {user_agent_info.browser.version_string}"
            os_info = f"{user_agent_info.os.family} {user_agent_info.os.version_string}"
        else:
            browser_info = "Không áp dụng"
            os_info = "Hệ thống"

        
        description_detail = f"Phát hiện file an ninh của '{ballot.title}' bị thay đổi. Hệ thống đã tự động phục hồi."
        diff_details = ""
        
        if backup_path:
            base_export_dir = os.path.dirname(os.path.dirname(backup_path))
            
            # --- LOGIC MỚI: TÌM ĐÚNG FILE BACKUP DỰA TRÊN LOẠI FILE ---
            if file_type == 'results':
                good_backup_path = get_backup_results_path(ballot.id, base_export_dir)
            else:
                good_backup_path = get_backup_file_path(ballot.id, base_export_dir)
            
            if os.path.exists(good_backup_path):
                # Lấy diff chi tiết dạng text để lưu vào CSDL
                diff_details = compare_files_and_get_diff(good_backup_path, backup_path)
                
                # Nếu là file kết quả, tạo mô tả có ý nghĩa hơn
                if file_type == 'results':
                    semantic_summary = compare_results_and_get_diff_summary(good_backup_path, backup_path)
                    description_detail = f"Phát hiện thay đổi trong file kết quả: {semantic_summary}."
            else:
                diff_details = "Không thể so sánh: File backup an toàn chưa tồn tại để đối chiếu."
        
        UserTamperLog.objects.create(
            description=description_detail,
            attempted_by=user if user and user.is_authenticated else None,
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

# def save_decrypted_blockchain_to_json(ballot, sorted_results, base_export_dir: str) -> tuple[bool, str]:
#     """
#     Hàm mới: Lưu kết quả đã được giải mã và kiểm đếm ra một file JSON công khai.
#     """
#     # Tạo một tên file riêng cho kết quả đã giải mã
#     original_path = get_blockchain_file_path(ballot.id, base_export_dir)
#     base, ext = os.path.splitext(os.path.basename(original_path))
#     decrypted_filename = f"{base}_decrypted_results.json"
#     decrypted_filepath = os.path.join(base_export_dir, decrypted_filename)

#     try:
#         # Tạo cấu trúc dữ liệu cho file kết quả
#         final_results_data = {
#             "ballot_id": ballot.id,
#             "ballot_title": ballot.title,
#             "tally_completed_at": timezone.localtime(timezone.now()).isoformat(),
#             "results": sorted_results
#         }

#         # Ghi dữ liệu vào file JSON
#         with open(decrypted_filepath, 'w', encoding='utf-8') as f:
#             json.dump(final_results_data, f, indent=4, ensure_ascii=False)
        
#         return True, f"Đã lưu thành công file kết quả đã giải mã: {decrypted_filename}"
#     except Exception as e:
#         return False, f"Lỗi khi lưu file JSON đã giải mã: {e}"
    

