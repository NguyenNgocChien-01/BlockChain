# quanly/blockchain_core.py

import hashlib
import json
import time
from django.utils import timezone

class VoteTransaction:
    """
    Đại diện cho một giao dịch phiếu bầu trong một khối.
    """
    def __init__(self, vote_id, encrypted_vote, voter_public_key, signature, timestamp):
        self.vote_id = vote_id
        self.encrypted_vote = encrypted_vote 
        self.voter_public_key = voter_public_key
        self.signature = signature
        self.timestamp = timestamp

    def to_dict(self):
        return self.__dict__

    @classmethod
    def from_dict(cls, data):
        # Logic này giúp hệ thống tương thích ngược với các file JSON cũ
        if 'voter_id_prefix' in data and 'voter_public_key' not in data:
            data['voter_public_key'] = data.pop('voter_id_prefix')
            
        return cls(**data)

class Block:
    """Định nghĩa cấu trúc của một khối trong chuỗi."""
    # --- SỬA LỖI: Thêm hash_value để tránh tính toán lại hash không cần thiết ---
    def __init__(self, index, transactions, previous_hash, difficulty, timestamp=None, nonce=0, hash_value=None):
        self.index = index
        self.timestamp = timestamp or timezone.localtime(timezone.now()).isoformat()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.difficulty = difficulty
        self.nonce = nonce
        # Chỉ tính hash nếu nó không được cung cấp (tức là khi tạo khối mới)
        self.hash = hash_value if hash_value is not None else self.calculate_hash()

    def calculate_hash(self):
        """Tính toán hash của khối dựa trên nội dung của nó."""
        tx_list_of_dicts = [tx.to_dict() for tx in self.transactions]
        tx_str = json.dumps(tx_list_of_dicts, sort_keys=True)
        
        value = f"{self.index}{self.timestamp}{tx_str}{self.previous_hash}{self.nonce}{self.difficulty}"
        return hashlib.sha256(value.encode()).hexdigest()

    def mine_block(self):
        """Thực hiện Proof-of-Work để tìm hash hợp lệ."""
        prefix_str = '0' * self.difficulty
        # Gán lại hash ban đầu trước khi đào
        self.hash = self.calculate_hash()
        while not self.hash.startswith(prefix_str):
            self.nonce += 1
            self.hash = self.calculate_hash()
        print(f"Đào thành công khối #{self.index} với hash: {self.hash}")

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "previous_hash": self.previous_hash,
            "difficulty": self.difficulty,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data):
        # --- SỬA LỖI: Truyền hash_value trực tiếp vào constructor ---
        transactions = [VoteTransaction.from_dict(tx) for tx in data["transactions"]]
        return cls(
            index=data["index"],
            timestamp=data["timestamp"],
            transactions=transactions,
            previous_hash=data["previous_hash"],
            difficulty=data["difficulty"],
            nonce=data["nonce"],
            hash_value=data["hash"] # Truyền hash đã có để không phải tính lại
        )

class Blockchain:
    """Quản lý toàn bộ chuỗi khối."""
    def __init__(self, difficulty=2):
        self.chain = []
        self.difficulty = difficulty

    def get_latest_block(self):
        return self.chain[-1] if self.chain else None

    def add_block(self, transactions):
        """Tạo khối mới, đào và thêm vào chuỗi."""
        latest_block = self.get_latest_block()
        previous_hash = latest_block.hash if latest_block else "0"
        new_block = Block(
            index=len(self.chain),
            transactions=transactions,
            previous_hash=previous_hash,
            difficulty=self.difficulty,
        )
        new_block.mine_block() # Đào khối
        self.chain.append(new_block)
        return new_block

    def is_chain_valid(self):
        """
        Kiểm tra tính toàn vẹn của toàn bộ chuỗi.
        """
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]

            if current_block.hash != current_block.calculate_hash():
                return False, f"Nội dung của khối #{current_block.index} đã bị thay đổi."

            if current_block.previous_hash != previous_block.hash:
                return False, f"Liên kết chuỗi bị phá vỡ tại khối #{current_block.index}."

        return True, "Chuỗi hợp lệ."

    def to_dict_list(self):
        return [block.to_dict() for block in self.chain]

    @classmethod
    def from_dict_list(cls, chain_data, difficulty=2):
        blockchain = cls(difficulty)
        blockchain.chain = [Block.from_dict(block_data) for block_data in chain_data]
        return blockchain
