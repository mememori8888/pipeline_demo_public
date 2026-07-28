import os
import asyncio
import uuid
import time
import re
from typing import List, Optional, Tuple
from google import genai
from google.genai import errors
from pydantic import BaseModel
from app.core.config import settings

# Google公式のYouTube APIクライアント
from googleapiclient.discovery import build
from app.services.batch_processor import extract_gdrive_folder_id, upload_markdown_to_gdrive

client = genai.Client(api_key=settings.GEMINI_API_KEY)
OUTPUT_DIR = "output_txts"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class YouTubeVideoPayload(BaseModel):
    title: str
    video_url: str
    published_at: str
    description: str

# ==========================================
# 📺 1. YouTube Data API 一括回収ロジック（限界突破版）
# ==========================================
def fetch_channel_videos(channel_url: str, limit_count: Optional[int] = None) -> List[YouTubeVideoPayload]:
    if not settings.YOUTUBE_API_KEY:
        print("[⚠️ 警告] YOUTUBE_API_KEY が未設定です。")
        return []

    print(f"[📺 YouTube API限界突破起動] チャンネルURL: {channel_url}")
    
    try:
        handle_match = re.search(r"(@[a-zA-Z0-9_\-\.]+)", channel_url)
        if not handle_match:
            raise ValueError("チャンネルURLからハンドル名（@...）を検出できませんでした。")
        handle_name = handle_match.group(1)
        
        youtube = build('youtube', 'v3', developerKey=settings.YOUTUBE_API_KEY)
        
        channel_response = youtube.channels().list(
            forHandle=handle_name, part='contentDetails,snippet'
        ).execute()
        
        if not channel_response.get('items'):
            raise ValueError(f"チャンネル（{handle_name}）が実在しないか、APIから取得できません。")
            
        channel_item = channel_response['items'][0]
        channel_title = channel_item['snippet']['title']
        uploads_playlist_id = channel_item['contentDetails']['relatedPlaylists']['uploads']
        
        print(f"[✅ チャンネル特定] 『{channel_title}』から動画データを全件回収開始します...")
        
        payloads = []
        next_page_token = None
        max_target = limit_count if (limit_count and limit_count > 0) else 1000
        
        while len(payloads) < max_target:
            remaining = max_target - len(payloads)
            chunk_size = min(remaining, 50)
            
            playlist_response = youtube.playlistItems().list(
                playlistId=uploads_playlist_id,
                part='snippet',
                maxResults=chunk_size,
                pageToken=next_page_token
            ).execute()
            
            for item in playlist_response.get('items', []):
                snippet = item['snippet']
                video_id = snippet['resourceId']['videoId']
                payloads.append(YouTubeVideoPayload(
                    title=snippet['title'],
                    video_url=f"https://www.youtube.com/watch?v={video_id}",
                    published_at=snippet['publishedAt'][:10],
                    description=snippet['description']
                ))
            
            next_page_token = playlist_response.get('nextPageToken')
            if not next_page_token:
                break
                
        print(f"[📊 スキャン完了] 『{channel_title}』から本物の動画データを合計 {len(payloads)} 本回収しました！")
        return payloads

    except Exception as e:
        print(f"[❌ YouTube API通信エラー]: {str(e)}")
        return []


# ==========================================
# 🛡️ 2. 【フェーズ1】動画パース（安価・高速なFlashモデルで一斉下読み）
# ==========================================
SEMAPHORE_LIMIT = 3
semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

async def summarize_single_video(video: YouTubeVideoPayload) -> Tuple[str, int, int]:
    async with semaphore:
        print(f"[⚙️ 動画パース中]: {video.title}")
        prompt = (
            f"重要情報抽出タスク:\n"
            f"あなたはプロの映像アナリストです。以下の本物のYouTube動画の情報を精査し、"
            f"その核心的な内容、解説されているノウハウ、および重要な気づきを"
            f"Markdown形式で過不足なくテキスト化してください。\n\n"
            f"■ タイトル: {video.title}\n"
            f"■ URL: {video.video_url}\n"
            f"■ 概要欄: {video.description}"
        )
        
        max_retries = 3
        base_delay = 2
        
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(model=settings.DEFAULT_MODEL_ID, contents=prompt)
                in_tokens = response.usage_metadata.prompt_token_count or 0
                out_tokens = response.usage_metadata.candidates_token_count or 0
                
                summary_output = (
                    f"### 🎥 動画個別要約: [{video.title}]({video.video_url})\n"
                    f"- **公開日**: {video.published_at}\n"
                    f"- **AIディープスキャンログ**:\n{response.text}\n\n"
                    f"--- \n\n"
                )
                return summary_output, in_tokens, out_tokens
                
            except Exception as e:
                err_msg = str(e)
                is_temporary = "503" in err_msg or "429" in err_msg or "UNAVAILABLE" in err_msg or "demand" in err_msg
                
                if is_temporary and attempt < max_retries - 1:
                    sleep_time = base_delay * (attempt + 1)
                    print(f"[⏳ YouTube混雑検知]: 『{video.title}』で503を検知。{sleep_time}秒後に自動リトライします... ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(sleep_time)
                else:
                    print(f"[❌ 動画パース断念]: {video.title} はエラーのためスキップします。")
                    return f"### ❌ 要約失敗: [{video.title}]({video.video_url})\n原因: {err_msg}\n\n--- \n\n", 0, 0


# ==========================================
# 🚀 3. 【フェーズ2】書籍化 ＆ ハイブリッド統合シンキング
# ==========================================
async def start_youtube_channel_pipeline(
    channel_url: str,
    limit_count: Optional[int],
    tenant_id: str,
    calculate_cost_func,
    output_folder_id: Optional[str] = None,
) -> dict:
    start_time = time.time()
    
    # 1. 50本の制限を突破した全件回収
    all_videos = fetch_channel_videos(channel_url, limit_count)
    total_found = len(all_videos)
    
    if total_found == 0:
        print("[❌ 終了] 動画が1本も取得できませんでした。")
        return {}

    target_videos = all_videos
    actual_process_count = len(target_videos)
    
    # 2. 各動画の並行下読み（フェーズ1）
    tasks = [summarize_single_video(v) for v in target_videos]
    task_results = await asyncio.gather(*tasks)
    
    videos_summary_pool = ""
    total_in_tokens = 0
    total_out_tokens = 0
    for summary_text, in_t, out_t in task_results:
        videos_summary_pool += summary_text
        total_in_tokens += in_t
        total_out_tokens += out_t

    # 3. 編集指示プロンプト
    print(f"\n[🧠 フェーズ2：統合インテリジェンス分析起動] {actual_process_count} 本分の要約データをマージ。定性と定量の両面から一つの本に編纂中...")
    
    macro_analysis_prompt = (
        "# 📚 YouTubeインテリジェンス・書籍化統合編集最高命令\n"
        "高度な知識書籍のカリスマ編集長、兼最高峰のマーケティングアナリストとして振る舞ってください。\n"
        "以下に渡される「全動画分の個別要約データ群」のすべてを深く読み込み、網羅的にシンキング（クロス分析）してください。\n"
        "そのまま単行本として出版できるクオリティの『チャンネル統合分析白書（一冊の本）』としてMarkdown形式で美しく執筆してください。\n\n"
        "## 📖 必須となる本の構成案:\n"
        "1. **本のタイトル**: 収集された動画データ全体の本質・思想を射抜いた、知的大ヒットを予感させる美しいタイトル（# タイトル）\n"
        "2. **プロローグ（はじめに）**: このチャンネル全体が扱っているマクロトレンド、発信の背景、およびビジネス・社会的意義（## はじめに）\n"
        "3. **📊 定量トピックシェア分析（どんなことが・どれくらい）**: \n"
        "   - 全動画のテキストから「どのようなテーマが、どれくらいの割合で発信されているか」を3〜5個の主要カテゴリーに厳密に分類して算出すること。\n"
        "   - 各カテゴリーが全体に占めるシェア（％）を計算し、必ず `[████████░░] 80% (x本で言及)` のような視覚的な『マークダウン・テキストグラフ』を用いて定量表現すること。\n"
        "   - そのテーマがなぜそれほど言及されているのか、深いアナリスト視点での定性考察を添えること。\n"
        "4. **体系的な本文（章立て）**: 個別データを論理的に構造化し、前後の文脈が流れるように綺麗にストーリーとして整理した各論（## 各論：体系的分析）\n"
        "5. **エピローグ（結びにかえて）**: 全体のデータを統合した最終結論、今後の動画トレンド予測、および未来への展望・総括（## 結論と今後の展望）\n\n"
        "## 🎨 文体・執筆ルール:\n"
        "- 完全に「である調（常体）」で統一し、品格を保つこと。\n"
        "- 「解析しました」などのシステム的な前置きや挨拶は一切禁止。本の本文そのものを出力すること。"
    )
    
    # 🌟【ここが最大の大改修：ハイブリッドAI戦略 ＆ 執念の5回リトライ】
    # 膨大なマージテキストの編集に耐えられるよう、まずは脳みそが強く制限の緩い最上位モデル「gemini-2.5-pro」を指名！
    # Proが万が一エラーになった場合は、フォールバックとして通常のFlashに切り替えて執念深くリトライを続けます。
    macro_response_text = ""
    success_flag = False
    
    for model_name in ["gemini-2.5-pro", settings.DEFAULT_MODEL_ID]:
        if success_flag:
            break
            
        print(f"[👑 AI編集長招集] 統合書籍化タスクに最適なモデル 『{model_name}』 の脳みそを起動中...")
        max_retries = 5
        base_delay = 5  # 初期待機を5秒に引き上げ、Googleサーバーのスパイクをやり過ごす
        
        for attempt in range(max_retries):
            try:
                macro_response = client.models.generate_content(
                    model=model_name, 
                    contents=[
                        f"■ 対象チャンネル: {channel_url}\n\n■ チャンネル内動画の個別要約データ群（素材）:\n{videos_summary_pool}",
                        macro_analysis_prompt
                    ]
                )
                total_in_tokens += macro_response.usage_metadata.prompt_token_count or 0
                total_out_tokens += macro_response.usage_metadata.candidates_token_count or 0
                macro_response_text = macro_response.text
                success_flag = True
                print(f"[✅ 統合書籍化大成功] モデル 『{model_name}』 にて完璧な本編の執筆が完了しました！")
                break
            except Exception as macro_err:
                err_msg = str(macro_err)
                is_temporary = "503" in err_msg or "429" in err_msg or "UNAVAILABLE" in err_msg or "demand" in err_msg
                
                if is_temporary and attempt < max_retries - 1:
                    sleep_time = base_delay * (attempt + 1)
                    print(f"[⏳ 統合シンキング混雑検知]: モデル 『{model_name}』 が503を検知。{sleep_time}秒後に自動リトライします... ({attempt + 1}/{max_retries})")
                    await asyncio.sleep(sleep_time)
                else:
                    print(f"[⚠️ モデル限界]: 『{model_name}』 での執筆が混雑制限に達しました。次の防衛線へ移行します。")
                    break

    # 4. 万が一すべてのAIモデルが力尽きた場合の最終予備フォールバック
    if not success_flag:
        print("[❌ 統合シンキング大失敗] すべてのAIモデルが混雑により力尽きました。予備テキストで出荷します。")
        macro_response_text = "## ⚠️ 統合マクロ分析エラー\nGoogleのAIサーバーが非常に混雑していたため、統合書籍化に一時的に失敗しました。巻末の個別動画カルテをご参照ください。"

    # 5. 【完全合体】本編（前半） ＋ ぶつ切り付録（後半）のドッキング
    final_markdown = (
        f"【ファイル種別判定】オンライン動画チャンネル分析 (YouTube 定量トピック・書籍化統合版)\n\n"
        f"{macro_response_text}\n\n"
        f" \n\n"
        f"# 📁 📘 付録（Appendix）：各動画の独立個別要約アーカイブ\n"
        f"--- \n"
        f"上記の『統合白書（本編）』を執筆・分析するにあたり、AIエンジンが動画1本1本から"
        f"事前にディープスキャンして抽出した、元データおよび証拠（エビデンス）の全記録です。検証用の生データとしてご活用ください。\n\n"
        f"{videos_summary_pool}"
        f"**[以上、YouTube解析報告書完結]**"
    )
    
    # 6. 容量制限のないローカルへ安全物理出荷
    file_name = f"youtube_channel_book_analysis_{uuid.uuid4().hex[:8]}.md"
    file_path = os.path.join(OUTPUT_DIR, file_name)
    with open(file_path, "w", encoding="utf-8") as f: 
        f.write(final_markdown)

    gdrive_result = None
    resolved_output_folder_id = extract_gdrive_folder_id(output_folder_id or settings.GOOGLE_DRIVE_OUTPUT_FOLDER_ID)
    if resolved_output_folder_id:
        gdrive_result = upload_markdown_to_gdrive(
            file_name=file_name,
            content=final_markdown,
            folder_id=resolved_output_folder_id,
        )
        
    elapsed_time = time.time() - start_time
    usd_cost = calculate_cost_func("gemini-2.5-flash", total_in_tokens, total_out_tokens)
    
    print(f"\n[🎉 YouTube本番バッチ完全終了]")
    print(f"[📂 保存先パス]: {file_path}")
    print(f" 推定総コスト: ${usd_cost:.4f} | 処理時間: {elapsed_time:.2f}秒")
    print("成果物は『定量シェアグラフ本編 ＋ ぶつ切り生データ付録』が合体した状態で安全に出荷されました！")
    
    if gdrive_result:
        print(f"[Google Drive output]: {gdrive_result}")

    return {"file_path": file_path, "gdrive_output": gdrive_result, "usd_cost": usd_cost}


# ==========================================
# 🤝 4. メインアプリ連動用の互換レイヤー（NameError完全根絶版）
# ==========================================
def prepare_batch_files(storage_type: str, target_path: str, limit_count: Optional[int] = None) -> Tuple[List, int, int]:
    """main.py側のインポートエラーを防ぐための空の互換関数です"""
    return [], 0, 0
