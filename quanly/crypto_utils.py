# quanly/crypto_utils.py
import json
from tgalice import n_pk, n_sk # type: ignore

def generate_threshold_keys(num_members, threshold):

    # Tạo khóa công khai và các mảnh khóa bí mật
    public_key, secret_key_shares = n_pk(k=threshold, n=num_members)
    
    # Chuyển đổi sang định dạng JSON để có thể lưu trữ
    pk_json = public_key.to_json()
    sk_shares_json = [sk.to_json() for sk in secret_key_shares]
    
    return pk_json, sk_shares_json

def encrypt_vote(public_key_json: str, candidate_ids: list) -> str:

    public_key = n_pk.from_json(public_key_json)
    
    # Chuyển danh sách ID thành một chuỗi để mã hóa, ví dụ: "1,5,9"
    # Sắp xếp để đảm bảo tính nhất quán
    message_to_encrypt = ",".join(map(str, sorted(candidate_ids)))
    
    # Mã hóa thông điệp
    ciphertext = public_key.encrypt(message_to_encrypt)
    
    return ciphertext.to_json()

def create_decryption_share(key_share_json: str, ciphertext_json: str) -> str:

    key_share = n_sk.from_json(key_share_json)
    ciphertext = n_pk.ciphertext_from_json(ciphertext_json)
    
    decryption_share = key_share.decrypt_share(ciphertext)
    
    return decryption_share.to_json()

def combine_decryption_shares(public_key_json: str, decryption_shares_json_list: list) -> str:

    public_key = n_pk.from_json(public_key_json)
    decryption_shares = [n_sk.decryption_share_from_json(s) for s in decryption_shares_json_list]
    
    # Giải mã thông điệp
    decrypted_message = public_key.decrypt(decryption_shares)
    
    return str(decrypted_message)
