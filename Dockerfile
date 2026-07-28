# 1. 2026年最新の軽量なPython 3.12公式イメージをベースに使用
FROM python:3.12-slim

# 2. コンテナ内の作業ディレクトリを「/app」に固定
WORKDIR /app

# 3. コンテナ内の出力をリアルタイムに確認できるよう、バッファを無効化
ENV PYTHONUNBUFFERED=1

# 4. まずはパッケージリストだけをコピーしてキャッシュを最大活用
COPY requirements.txt .

# 5. パッケージを高速かつキャッシュなしでクリーンにインストール
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. あなたが作った自慢のローカルコード（appフォルダなど）を丸ごとコンテナへ複製
COPY . .

# 7. Cloud Runのポート自動割り当て（デフォルト8080）に完全対応させる設定
ENV PORT=8080

# 8. 運命のコンテナ起動コマンド（sh -c を挟むことで、Cloud Runから渡される動的PORTに100%追従します）
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]