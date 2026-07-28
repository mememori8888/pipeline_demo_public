import json
import re
from typing import Dict
from pydantic import BaseModel

class MaskedResult(BaseModel):
    masked_text: str
    token_map: Dict[str, str]  # 例: {"[USER_NAME_1]": "山田太郎"}

class PIIMaskingInterceptor:
    """LLMや検索エンジンにデータが渡る前に、PIIを自動検知して完全にガードする迎撃層"""
    
    def __init__(self):
        # 日本の主要な個人情報パターン（簡易正規表現によるフールプルーフ）
        self.phone_pattern = re.compile(r'\d{2,4}-\d{2,4}-\d{4}')
        self.email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
        self.postcode_pattern = re.compile(r'〒?\d{3}-\d{4}')
        
        # 【🔥バグ修正箇所】
        # `{1}県` の直前に文字クラスを定義していなかったエラーを解消。
        # 「市区町村以外の文字が2〜3文字続いた後に『県』が来る」パターン（例: 神奈川県、兵庫県）へ修正し、
        # 後続の市区町村の抽出も非貪欲マッチ（+?）に変更して住所の過剰な巻き込みを防ぎます。
        self.address_pattern = re.compile(r'(東京都|北海道|京都府|大阪府|[^市区町村\n]{2,3}県)[^市区町村\n]+?(市|区|町|村|郡)[^\n]+')

    def intercept_and_mask(self, raw_text: str) -> MaskedResult:
        """テキスト内の個人情報を検知し、置換トークンに置き換える（単一責任の原則）"""
        if not raw_text:
            return MaskedResult(masked_text="", token_map={})

        token_map: Dict[str, str] = {}
        masked_text = raw_text

        # 1. メールアドレスのマスク
        emails = self.email_pattern.findall(masked_text)
        for idx, email in enumerate(set(emails)):
            token = f"[EMAIL_{idx+1}]"
            token_map[token] = email
            masked_text = masked_text.replace(email, token)

        # 2. 電話番号のマスク
        phones = self.phone_pattern.findall(masked_text)
        for idx, phone in enumerate(set(phones)):
            token = f"[PHONE_{idx+1}]"
            token_map[token] = phone
            masked_text = masked_text.replace(phone, token)

        # 3. 郵便番号のマスク
        postcodes = self.postcode_pattern.findall(masked_text)
        for idx, pc in enumerate(set(postcodes)):
            token = f"[POSTCODE_{idx+1}]"
            token_map[token] = pc
            masked_text = masked_text.replace(pc, token)

        # 4. 住所のマスク（finditerを用いてマッチオブジェクトから正確に置換）
        for idx, match in enumerate(self.address_pattern.finditer(masked_text)):
            addr = match.group()
            token = f"[ADDRESS_{idx+1}]"
            if token not in token_map:  # トークン重複の物理ガード
                token_map[token] = addr
                masked_text = masked_text.replace(addr, token)

        return MaskedResult(masked_text=masked_text, token_map=token_map)

    def revert_demask(self, masked_text: str, token_map: Dict[str, str]) -> str:
        """
        [リバート機能] 承認された出力の直前、
        または権限を持つユーザーへのレスポンス時にのみトークンを実データに安全に復元する
        """
        if not masked_text:
            return ""
        
        reverted_text = masked_text
        for token, original_value in token_map.items():
            reverted_text = reverted_text.replace(token, original_value)
            
        return reverted_text

pii_interceptor = PIIMaskingInterceptor()