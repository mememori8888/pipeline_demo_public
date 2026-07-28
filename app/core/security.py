import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from app.core.config import settings

class CryptoEngine:
    """AES-256 CBCモードによるデータ暗号化・復号化エンジン"""
    def __init__(self):
        # 32バイトの鍵を確実に生成
        self.key = settings.ENCRYPTION_KEY.encode('utf-8')[:32].ljust(32, b'\0')

    def encrypt(self, plain_text: str) -> str:
        if not plain_text:
            return ""
        cipher = AES.new(self.key, AES.MODE_CBC)
        iv = cipher.iv
        padded_data = pad(plain_text.encode('utf-8'), AES.block_size)
        encrypted_data = cipher.encrypt(padded_data)
        # IVと暗号文を一緒にしてbase64エンコード
        return base64.b64encode(iv + encrypted_data).decode('utf-8')

    def decrypt(self, encrypted_base64: str) -> str:
        if not encrypted_base64:
            return ""
        try:
            raw_data = base64.b64decode(encrypted_base64.encode('utf-8'))
            iv = raw_data[:AES.block_size]
            encrypted_content = raw_data[AES.block_size:]
            cipher = AES.new(self.key, AES.MODE_CBC, iv)
            decrypted_padded = cipher.decrypt(encrypted_content)
            return unpad(decrypted_padded, AES.block_size).decode('utf-8')
        except Exception as e:
            # フェイルセーフ：復号失敗時はシステムをクラッシュさせず空文字またはエラーログハンドリング
            return f"[DECRYPTION_FAILED: {str(e)}]"

crypto_engine = CryptoEngine()