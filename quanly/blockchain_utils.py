import hashlib
import json
import os
from django.conf import settings
from django.utils import timezone
from quanly.models import Block, Ballot # Đảm bảo đã import đúng các models này
import unicodedata # Để xử lý ký tự có dấu


# --- HÀM HỖ TRỢ TÍNH TOÁN CHECKSUM VÀ ĐƯỜNG DẪN FILE ---

# Hàm này vẫn giữ lại nếu cần dùng cho mục đích khác
def calculate_file_checksum(filepath: str) -> str:
    """Tính toán SHA256 hash của nội dung file."""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()

def get_blockchain_file_path(ballot_id: int, base_export_dir: str) -> str:
    """
    Trả về đường dẫn tới file JSON blockchain cho một cuộc bầu cử riêng lẻ.
    base_export_dir: Thư mục gốc để lưu trữ (ví dụ: save_blockchain_per_ballot).
    """
    os.makedirs(base_export_dir, exist_ok=True)
    
    try:
        ballot_obj = Ballot.objects.get(id=ballot_id)
    except Ballot.DoesNotExist:
        return os.path.join(base_export_dir, f"blockchain_unknown_ballot_{ballot_id}.json")

    normalized_title = unicodedata.normalize('NFD', ballot_obj.title)
    ascii_only_title = normalized_title.encode('ascii', 'ignore').decode('utf-8')
    safe_ballot_title = ascii_only_title.replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_').lower()
    
    file_name = f"blockchain_{safe_ballot_title}_{ballot_id}.json"
    return os.path.join(base_export_dir, file_name)


# --- HÀM LƯU VÀ XÁC MINH (CHO TỪNG CUỘC BẦU CỬ) ---

def save_blockchain_to_json_with_integrity_check(ballot_id: int, base_export_dir: str) -> tuple[bool, str]:
    """
    Xuất toàn bộ blockchain của một cuộc bầu cử ra file JSON.
    Giá trị chain_hash (checksum) được lưu TRONG file JSON.
    """
    blockchain_file_path = get_blockchain_file_path(ballot_id, base_export_dir)

    try:
        ballot_obj = Ballot.objects.get(id=ballot_id)

        blockchain_blocks = Block.objects.filter(ballot=ballot_obj).order_by('id').prefetch_related('votes__candidate')

        if not blockchain_blocks.exists():
            return True, f"Không tìm thấy khối nào cho Cuộc Bầu Cử '{ballot_obj.title}'. Bỏ qua việc xuất file."

        blockchain_data_list = [block.to_json_serializable() for block in blockchain_blocks]

        # 1. Tính toán chain_hash của MẢNG 'blocks'
        # Đảm bảo dữ liệu được sắp xếp (sort_keys=True) để hash luôn nhất quán
        full_blocks_json_string = json.dumps(blockchain_data_list, indent=4, ensure_ascii=False, sort_keys=True)
        chain_hash_of_blocks = hashlib.sha256(full_blocks_json_string.encode('utf-8')).hexdigest()

        # 2. Tạo cấu trúc dữ liệu xuất cuối cùng, bao gồm 'chain_hash' ở cấp cao nhất
        full_export_data = {
            "ballot_id": ballot_obj.id,
            "ballot_title": ballot_obj.title,
            "exported_at": timezone.now().isoformat(),
            "chain_hash": chain_hash_of_blocks, # <-- CHUỖI CHECKSUM ĐƯỢC LƯU Ở ĐÂY
            "blocks": blockchain_data_list # Danh sách các block
        }

        # 3. Ghi toàn bộ dữ liệu vào file JSON
        with open(blockchain_file_path, 'w', encoding='utf-8') as f:
            json.dump(full_export_data, f, indent=4, ensure_ascii=False)
        
        return True, f"Blockchain của bầu cử '{ballot_obj.title}' đã được lưu thành công vào file: {blockchain_file_path} (chain_hash được nhúng)."
    except Ballot.DoesNotExist:
        return False, f"Lỗi: Không tìm thấy cuộc bầu cử với ID {ballot_id}."
    except Exception as e:
        return False, f"Lỗi khi lưu blockchain vào JSON: {e}"

def verify_blockchain_integrity(ballot_id: int, base_export_dir: str) -> tuple[bool, str]:
    """
    Kiểm tra tính toàn vẹn của file blockchain JSON bằng cách xác minh chain_hash nội bộ.
    Phát hiện sửa đổi dữ liệu bên trong file.
    """
    blockchain_file_path = get_blockchain_file_path(ballot_id, base_export_dir)

    if not os.path.exists(blockchain_file_path):
        return False, "File blockchain không tồn tại."

    try:
        with open(blockchain_file_path, 'r', encoding='utf-8') as f:
            full_export_data = json.load(f) # Tải toàn bộ nội dung JSON
        
        # 1. Kiểm tra cấu trúc file và lấy các trường cần thiết
        if "blocks" not in full_export_data or "chain_hash" not in full_export_data:
            return False, "File blockchain bị thiếu trường 'blocks' hoặc 'chain_hash'."

        stored_chain_hash = full_export_data["chain_hash"]
        blocks_data = full_export_data["blocks"]

        # 2. Tái tạo chuỗi JSON của mảng 'blocks' và tính toán lại hash
        # PHẢI DÙNG CÙNG CÁC THAM SỐ NHƯ LÚC LƯU (indent, ensure_ascii, sort_keys)
        recalculated_blocks_json_string = json.dumps(blocks_data, indent=4, ensure_ascii=False, sort_keys=True)
        current_chain_hash = hashlib.sha256(recalculated_blocks_json_string.encode('utf-8')).hexdigest()

        # 3. So sánh hash đã lưu với hash vừa tính
        if stored_chain_hash == current_chain_hash:
            return True, "Blockchain đảm bảo tính toàn vẹn (chain_hash nội bộ hợp lệ)."
        else:
            return False, "Blockchain đã bị sửa đổi! Chain_hash nội bộ không khớp."
    except json.JSONDecodeError:
        return False, "File blockchain bị hỏng định dạng JSON."
    except Exception as e:
        return False, f"Lỗi khi đọc hoặc xác minh file blockchain: {e}"