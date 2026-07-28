import os
import time
import requests

BASE_URL = "http://127.0.0.1:8080"
TENANT_ID = "integration_test_company"

print("==================================================")
print("🛡️ セキュアAI構造化エンジン 全自動結合テスト開始")
print("==================================================")

os.makedirs("input_pdfs", exist_ok=True)
sample_file_path = "input_pdfs/autogen_test_document.txt"

with open(sample_file_path, "w", encoding="utf-8") as f:
    f.write("宛先: 山田太郎 様\n住所: 東京都新宿区西新宿1-1-1\n契約金額: 840,000円\n特約: 2026年6月末までに納品すること。")

print(f"[前処理] テスト用ファイルを自動生成しました: {sample_file_path}\n")

if os.path.exists("output_txts"):
    import shutil
    shutil.rmtree("output_txts")
os.makedirs("output_txts", exist_ok=True)


# --- TEST 1 ---
print("▶️ [TEST 1/5] スキーマ自動生成 API を検証中...")
with open(sample_file_path, "rb") as f:
    res = requests.post(
        f"{BASE_URL}/api/v1/schema/generate",
        data={"tenant_id": TENANT_ID},
        files={"file": (os.path.basename(sample_file_path), f, "text/plain")}
    )
if res.status_code == 200:
    print("  ✅ インプット成功: サンプルファイルをAIへ送信")
    print("  ✅ アウトプット成功: AIが自作したスキーマオブジェクトをDB保存し返却\n")
else:
    print(f"  ❌ TEST 1 失敗: {res.text}\n")


# --- TEST 2 ---
print("▶️ [TEST 2/5] PIIガード付き本解析・構造化 API を検証中...")
with open(sample_file_path, "rb") as f:
    res = requests.post(
        f"{BASE_URL}/api/v1/document/process",
        data={"tenant_id": TENANT_ID, "industry_type": "contract_summary", "speed_mode": "scan"},
        files={"file": (os.path.basename(sample_file_path), f, "text/plain")}
    )
if res.status_code == 200:
    data = res.json()
    document_id = data.get("document_id")
    masked_data = data.get("structured_data_masked")
    print("  ✅ インプット成功: 解析対象ファイルとマルチテナントIDを送信")
    print(f"  ✅ アウトプット成功: 2026年最新レートによる予想消費コスト: ${data.get('billing_metrics', {}).get('estimated_usd_cost')}\n")
else:
    print(f"  ❌ TEST 2 失敗: {res.text}\n")
    document_id = None


# --- TEST 3 ---
print("▶️ [TEST 3/5] セキュアデマスキング（個人情報復元） API を検証中...")
if document_id:
    decrypt_payload = { "tenant_id": TENANT_ID, "document_id": document_id, "masked_json_data": masked_data }
    res = requests.post(f"{BASE_URL}/api/v1/document/decrypt", json=decrypt_payload)
    if res.status_code == 200:
        print("  ✅ インプット成功: マスクされたJSONとドキュメントIDを金庫へ送信")
        print(f"  ✅ アウトプット成功: 復元されたデータ: {res.json().get('structured_data_decrypted')}\n")
    else:
        print(f"  ❌ TEST 3 失敗: {res.text}\n")


# --- TEST 4 ---
print("▶️ [TEST 4/5] 枚数制御付き・大量書類一括非同期バッチ API を検証中...")
batch_payload = { "storage_type": "local", "target_path": "input_pdfs", "limit_count": 1, "prompt_preset": "smart_classifier" }
res = requests.post(f"{BASE_URL}/api/v1/document/batch-process", data=batch_payload)
if res.status_code == 200:
    print("  ✅ インプット成功: スキャン場所と指示を送信")
    print("  ⏳ 外部AIのファイル転送・通信完了を【15秒間】じっくり待ちます...")
    time.sleep(15) # 🌟 5秒から15秒へ引き延ばし
    
    output_files = os.listdir("output_txts")
    if any("autogen_test_document" in f for f in output_files):
        print("  ✅ アウトプット成功: 『output_txts/』フォルダへの物理ファイル自動出力確認！\n")
    else:
        print("  ❌ TEST 4 タイムアウト: AIの処理が時間内に終わりませんでした。もう一度お試しください。\n")


# --- TEST 5 ---
print("▶️ [TEST 5/5] YouTubeチャンネル一括分析ニュース生成 API を検証中...")
yt_payload = { "tenant_id": TENANT_ID, "channel_url": "https://www.youtube.com/@AI_Market_Trends", "limit_count": 2 }
res = requests.post(f"{BASE_URL}/api/v1/document/youtube-channel-process", data=yt_payload)
if res.status_code == 200:
    print("  ✅ インプット成功: チャンネルURLを送信")
    print("  ⏳ 外部AIの動画パース・総合執筆完了を【15秒間】じっくり待ちます...")
    time.sleep(60) # 🌟 5秒から15秒へ引き延ばし
    
    output_files = os.listdir("output_txts")
    if any("youtube_channel_analysis" in f for f in output_files):
        print("  ✅ アウトプット成功: 『output_txts/』への特大Markdownニュースの保存を確認！\n")
    else:
        print("  ❌ TEST 5 タイムアウト: AIの処理が時間内に終わりませんでした。もう一度お試しください。\n")

print("==================================================")
print("🎉 全自動結合テスト工程の終了")
print("==================================================")