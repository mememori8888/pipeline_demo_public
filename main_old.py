import streamlit as st
import asyncio
import time
import pandas as pd

# --- UI全体設定 ---
st.set_page_config(page_title="AI Multimodal Pipeline", layout="wide", page_icon="🚀")

# --- カスタムCSS (全体のデザインとPricingテーブルの装飾) ---
st.markdown("""
<style>
    /* 全体背景 */
    .main { background-color: #f8fafc; }
    
    /* Pricing用のカードスタイル */
    .price-card {
        background: white;
        padding: 1.5rem;
        border-radius: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 2rem;
        border: 1px solid #e2e8f0;
    }
    .model-header {
        color: #1e293b;
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        border-left: 5px solid #3b82f6;
        padding-left: 1rem;
        margin-bottom: 1.5rem;
        font-size: 1.5rem;
    }
    /* テーブルのデザイン */
    .pricing-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 1rem;
        font-size: 0.95rem;
    }
    .pricing-table th {
        background-color: #f1f5f9;
        color: #475569;
        text-align: left;
        padding: 12px;
        border-bottom: 2px solid #e2e8f0;
    }
    .pricing-table td {
        padding: 12px;
        border-bottom: 1px solid #f1f5f9;
        color: #334155;
    }
    .highlight-flash { color: #059669; font-weight: 700; }
    .highlight-pro { color: #7c3aed; font-weight: 700; }
    
    /* アドバイス用ボックス */
    .case-study {
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
        padding: 1.5rem;
        border-radius: 0.75rem;
        border: 1px solid #bfdbfe;
        color: #1e40af;
    }
</style>
""", unsafe_allow_html=True)

st.title("🚀 AI Multimodal & Data Pipeline")
st.markdown("ドキュメント解析、YouTube動画要約、そしてBigQueryでのデータ管理を統合した大規模処理システムです。")

# ==========================================
# サイドバー (API設定 & 技術スタックのアピール)
# ==========================================
with st.sidebar:
    st.header("🔑 Settings")
    gemini_key = st.text_input("Gemini API Key", type="password")
    youtube_key = st.text_input("YouTube API Key", type="password")
    
    st.divider()
    
    st.markdown("### 🛠️ Tech Stack & Architecture")
    with st.expander("詳細を見る", expanded=True):
        st.markdown("""
        - **Frontend**: [Streamlit](https://streamlit.io/)
        - **AI Engine**: Gemini 1.5 / 2.5 API
        - **Data Pipeline**:
          - YouTube Data API v3
          - `asyncio` (非同期並列処理)
        - **Storage**: Google Cloud BigQuery
        - **Design Patterns**: 
          - *Decorator* (A/B Test)
          - *Proxy* (Error Handling)
        """)
    st.caption("Developed by [Your Name] | 2026")

# --- 4つの機能タブを作成 ---
tab_doc, tab_yt, tab_db, tab_price = st.tabs([
    "📄 Document Parser", 
    "▶️ YouTube Summarizer (Batch)", 
    "📊 RAG Chat",
    "💎 API Pricing"
])

# ==========================================
# Tab 1: ドキュメント解析
# ==========================================
with tab_doc:
    st.subheader("PDF / Image to Markdown")
    uploaded_files = st.file_uploader("ファイルをアップロード", type=['pdf', 'jpg', 'png'], accept_multiple_files=True)
    
    if st.button("🚀 Analyze & Save to DB", key="doc_btn"):
        if not uploaded_files:
            st.warning("ファイルをアップロードしてください。")
        else:
            with st.spinner("Geminiが解析中..."):
                time.sleep(2) # ダミー
                st.success("解析とBigQueryへの保存が完了しました！")
                for file in uploaded_files:
                    with st.expander(f"✅ 解析結果: {file.name}", expanded=True):
                        st.markdown(f"### {file.name}の要約\nここにGeminiが生成した内容が表示されます。")
                        st.caption("※この内容はBigQueryにも保存されました")

# ==========================================
# Tab 2: YouTube パイプライン (大規模バッチ処理)
# ==========================================
with tab_yt:
    st.subheader("Channel to Summaries (Batch Processing)")
    st.markdown("指定したチャンネルの動画を非同期で一括取得し、Geminiで要約してBigQueryへ保存します。")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        channel_url = st.text_input("YouTube Channel URL (例: https://www.youtube.com/@channel_name)")
    with col2:
        max_videos = st.number_input("取得する最大動画数", min_value=1, max_value=1000, value=100, step=10)
    
    if st.button("▶️ Start Batch Processing", key="yt_btn", type="primary"):
        if not channel_url:
            st.warning("URLを入力してください。")
        else:
            with st.status(f"🚀 大規模バッチ処理を開始 (最大 {max_videos} 件)...", expanded=True) as status:
                st.write("🔍 YouTube API: 動画リストを取得中...")
                time.sleep(1)
                st.write(f"⚙️ asyncio: 並列ワーカーを起動中...")
                progress_bar = st.progress(0)
                for i in range(100):
                    time.sleep(0.02)
                    progress_bar.progress(i + 1)
                status.update(label="全件の要約とBigQueryへのINSERTが完了！", state="complete", expanded=False)
            st.success(f"{max_videos}本の動画処理が完了しました。")

# ==========================================
# Tab 3: RAG Chat (Knowledge Base)
# ==========================================
with tab_db:
    st.subheader("🤖 Chat with your Knowledge Base (RAG)")
    st.markdown("BigQueryに蓄積されたデータをベクトル検索し、根拠に基づいた回答を生成します。")
    
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "BigQueryのナレッジベースに接続しました。何でも質問してください！"}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("例: ガンジーの思想について教えて"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.status("🧠 RAG Pipeline 実行中...", expanded=True) as status:
                st.write("1. 質問をベクトル化...")
                time.sleep(0.5)
                st.write("2. BigQuery Vector Search を実行中...")
                time.sleep(0.5)
                status.update(label="回答生成完了", state="complete", expanded=False)
            
            response = "データベースの検索結果に基づくと、〇〇は△△であると記録されています。"
            st.markdown(response)
            st.caption("🔍 **Sources:** [https://youtube.com/watch?v=OJDCs6u5DM0]")
            st.session_state.messages.append({"role": "assistant", "content": response})

# ==========================================
# Tab 4: 💎 API Pricing (融合機能)
# ==========================================
with tab_price:
    st.subheader("💎 Gemini API 料金・トークン設計ガイド")
    st.markdown("システムの運用コストを把握し、モデルの選択を最適化します。")
    
    # 料金表セクション
    st.markdown("""
    <div class="price-card">
        <h3 class="model-header">100万トークンあたりの単価 (USD)</h3>
        <table class="pricing-table">
            <thead>
                <tr>
                    <th>モデル名</th>
                    <th>Input (1M tokens)</th>
                    <th>Output (1M tokens)</th>
                    <th>主な用途</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="highlight-flash">Gemini 2.5 Flash</td>
                    <td>$0.30</td>
                    <td>$2.50</td>
                    <td>大量要約、リアルタイム解析</td>
                </tr>
                <tr>
                    <td class="highlight-pro">Gemini 2.5 Pro</td>
                    <td>$1.25</td>
                    <td>$10.00</td>
                    <td>高度なRAG、複雑な論理推論</td>
                </tr>
            </tbody>
        </table>
    </div>
    
    <div class="price-card">
        <h3 class="model-header">メディア別トークン消費量</h3>
        <table class="pricing-table">
            <thead>
                <tr>
                    <th>メディア</th>
                    <th>計算単位</th>
                    <th>消費トークン数</th>
                </tr>
            </thead>
            <tbody>
                <tr><td>🖼️ 画像</td><td>1枚あたり</td><td>258</td></tr>
                <tr><td>🎥 動画</td><td>1秒あたり(1fps)</td><td>258</td></tr>
                <tr><td>🎙️ 音声</td><td>1秒あたり</td><td>32</td></tr>
                <tr><td>📄 PDF</td><td>1枚あたり</td><td>約 300 - 1,000</td></tr>
            </tbody>
        </table>
    </div>
    """, unsafe_allow_html=True)

    # シミュレーターセクション
    st.markdown("### 🧮 10分動画の解析コスト計算")
    col1, col2, col3 = st.columns(3)
    
    total_tokens = (600 * 258) + (600 * 32) # 10分
    price_flash = (total_tokens / 1000000) * 0.30 * 150
    price_pro = (total_tokens / 1000000) * 1.25 * 150
    
    col1.metric("推定総トークン数", f"{total_tokens:,}")
    col2.metric("Flash 料金", f"約 {price_flash:.1f} 円", delta="格安")
    col3.metric("Pro 料金", f"約 {price_pro:.1f} 円", delta="高品質")

    st.markdown("""
    <div class="case-study">
        <h4>💡 RAG開発に向けたアドバイス</h4>
        <ul>
            <li><b>バッチ要約:</b> 1000本単位のYouTube要約は <b>Flash</b> でコストを抑えるのが正攻法です。</li>
            <li><b>精度の担保:</b> RAGの最終回答生成のみ <b>Pro</b> を使うハイブリッド構成を推奨。</li>
            <li><b>今後の計画:</b> BigQueryに保存されたMarkdownを、Geminiのファインチューニング用データとして活用し、出力形式を完全に固定する予定です。</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)