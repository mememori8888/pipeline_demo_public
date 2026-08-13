from app.core.config import settings


def drive_folder_url(folder_id: str) -> str:
    folder_id = (folder_id or "").strip()
    if not folder_id:
        return "#"
    return f"https://drive.google.com/drive/folders/{folder_id}"


def render_operator_console() -> str:
    input_url = drive_folder_url(settings.GOOGLE_DRIVE_INPUT_FOLDER_ID)
    output_url = drive_folder_url(settings.GOOGLE_DRIVE_OUTPUT_FOLDER_ID)
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pipeline Demo Console</title>
  <style>
    :root {{
      --bg: #f5f7f8;
      --panel: #ffffff;
      --ink: #1d252c;
      --muted: #64717d;
      --line: #d9e0e5;
      --teal: #087f8c;
      --teal-dark: #05616b;
      --amber: #b87503;
      --red: #b42318;
      --green: #107569;
      --shadow: 0 12px 36px rgba(27, 39, 49, .08);
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background: var(--bg);
      font-family: Arial, "Hiragino Kaku Gothic ProN", "Yu Gothic", Meiryo, sans-serif;
      letter-spacing: 0;
    }}

    button, input, select, textarea {{
      font: inherit;
    }}

    .shell {{
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      min-height: 100vh;
    }}

    .sidebar {{
      background: #202a33;
      color: #f8fbfc;
      padding: 24px 20px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }}

    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      min-height: 44px;
    }}

    .mark {{
      width: 36px;
      height: 36px;
      border-radius: 8px;
      background: var(--teal);
      display: grid;
      place-items: center;
      font-weight: 700;
    }}

    h1 {{
      font-size: 18px;
      line-height: 1.25;
      margin: 0;
      font-weight: 700;
    }}

    .navlinks {{
      display: grid;
      gap: 8px;
    }}

    .navlinks a {{
      color: #dce8ec;
      text-decoration: none;
      padding: 10px 12px;
      border-radius: 8px;
      background: rgba(255,255,255,.06);
    }}

    .navlinks a:hover {{
      background: rgba(255,255,255,.12);
    }}

    .small {{
      color: #aebbc3;
      font-size: 13px;
      line-height: 1.5;
    }}

    main {{
      padding: 28px;
      display: grid;
      gap: 20px;
      align-content: start;
    }}

    .topbar {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      flex-wrap: wrap;
    }}

    .titleblock h2 {{
      font-size: 26px;
      margin: 0 0 6px;
    }}

    .titleblock p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
    }}

    .status-pill {{
      min-width: 128px;
      height: 38px;
      padding: 0 14px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--panel);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      color: var(--muted);
      font-weight: 700;
    }}

    .status-pill.ok {{ color: var(--green); }}
    .status-pill.warn {{ color: var(--amber); }}
    .status-pill.err {{ color: var(--red); }}

    .grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(320px, .75fr);
      gap: 20px;
      align-items: start;
    }}

    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 18px;
    }}

    .panel h3 {{
      margin: 0 0 14px;
      font-size: 17px;
    }}

    .form-grid {{
      display: grid;
      gap: 14px;
    }}

    label {{
      display: grid;
      gap: 7px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }}

    input, select, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 11px;
      color: var(--ink);
      background: #fff;
      min-height: 40px;
    }}

    textarea {{
      min-height: 96px;
      resize: vertical;
    }}

    .row {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}

    .actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 4px;
    }}

    button, .button-link {{
      border: 0;
      border-radius: 8px;
      min-height: 40px;
      padding: 0 14px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      background: var(--teal);
      color: white;
      text-decoration: none;
      cursor: pointer;
      font-weight: 700;
    }}

    button.secondary, .button-link.secondary {{
      color: var(--ink);
      background: #eef3f5;
      border: 1px solid var(--line);
    }}

    button:hover, .button-link:hover {{ filter: brightness(.96); }}
    button:disabled {{ opacity: .55; cursor: wait; }}

    .metrics {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }}

    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 13px;
      background: #fbfcfd;
      min-height: 82px;
    }}

    .metric strong {{
      display: block;
      font-size: 24px;
      line-height: 1.2;
    }}

    .metric span {{
      color: var(--muted);
      font-size: 12px;
    }}

    pre {{
      margin: 0;
      max-height: 360px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
      background: #17212a;
      color: #eef8fa;
      border-radius: 8px;
      padding: 14px;
      font-size: 13px;
      line-height: 1.45;
    }}

    .files {{
      display: grid;
      gap: 8px;
      margin-top: 12px;
    }}

    .file {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fbfcfd;
      display: flex;
      justify-content: space-between;
      gap: 12px;
    }}

    .file span {{
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }}

    @media (max-width: 900px) {{
      .shell {{ grid-template-columns: 1fr; }}
      .sidebar {{ min-height: auto; }}
      main {{ padding: 18px; }}
      .grid {{ grid-template-columns: 1fr; }}
      .metrics {{ grid-template-columns: 1fr; }}
      .row {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="mark">PD</div>
        <h1>Pipeline Demo<br>Console</h1>
      </div>
      <nav class="navlinks">
        <a href="{input_url}" target="_blank" rel="noreferrer">入力フォルダ</a>
        <a href="{output_url}" target="_blank" rel="noreferrer">出力フォルダ</a>
        <a href="/api/docs" target="_blank" rel="noreferrer">API Docs</a>
      </nav>
      <div class="small">Google Drive の入力フォルダを読み取り、解析結果を出力フォルダへ Markdown として保存します。</div>
    </aside>

    <main>
      <section class="topbar">
        <div class="titleblock">
          <h2>Drive Batch Operator</h2>
          <p>フォルダ状態を確認して、全件または指定件数の一括処理を開始します。</p>
        </div>
        <div id="healthPill" class="status-pill">checking</div>
      </section>

      <section class="grid">
        <div class="panel">
          <h3>実行</h3>
          <div class="form-grid">
            <label>
              API Key
              <input id="apiKey" type="password" autocomplete="off" placeholder="X-API-Key">
            </label>
            <div class="row">
              <label>
                処理件数
                <input id="limitCount" type="number" min="1" step="1" placeholder="空欄なら全件">
              </label>
              <label>
                分割サイズ
                <input id="chunkSize" type="number" min="1" step="1" value="5">
              </label>
              <label>
                プリセット
                <select id="promptPreset">
                  <option value="ocr_markdown">OCR Markdown</option>
                  <option value="smart_classifier">Smart Classifier</option>
                  <option value="contract_summary">Contract Summary</option>
                  <option value="image_risk_check">Image Risk Check</option>
                </select>
              </label>
            </div>
            <label>
              カスタム指示
              <textarea id="customPrompt" placeholder="任意。空ならプリセットを使用"></textarea>
            </label>
            <div class="actions">
              <button id="saveKeyBtn" type="button">保存</button>
              <button id="checkDriveBtn" class="secondary" type="button">Drive確認</button>
              <button id="startBatchBtn" type="button">処理開始</button>
              <a class="button-link secondary" href="{output_url}" target="_blank" rel="noreferrer">出力を開く</a>
            </div>
          </div>
        </div>

        <div class="panel">
          <h3>Drive 状態</h3>
          <div class="metrics">
            <div class="metric"><strong id="sampleCount">-</strong><span>入力ファイル</span></div>
            <div class="metric"><strong id="canList">-</strong><span>読み取り</span></div>
            <div class="metric"><strong id="canAdd">-</strong><span>出力追加</span></div>
          </div>
          <div id="fileList" class="files"></div>
        </div>
      </section>

      <section class="panel">
        <h3>結果</h3>
        <pre id="resultBox">Ready.</pre>
      </section>
    </main>
  </div>

  <script>
    const apiKeyInput = document.getElementById("apiKey");
    const resultBox = document.getElementById("resultBox");
    const healthPill = document.getElementById("healthPill");
    const savedKey = localStorage.getItem("pipelineDemoApiKey");
    if (savedKey) apiKeyInput.value = savedKey;

    function apiKey() {{
      return apiKeyInput.value.trim();
    }}

    function show(data) {{
      resultBox.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    }}

    function headers() {{
      const key = apiKey();
      return key ? {{ "X-API-Key": key }} : {{}};
    }}

    async function parseResponse(response) {{
      const text = await response.text();
      let body = text;
      try {{ body = JSON.parse(text); }} catch (_) {{}}
      if (!response.ok) {{
        throw {{ status: response.status, body }};
      }}
      return body;
    }}

    async function checkHealth() {{
      try {{
        const response = await fetch("/api/healthz");
        const data = await parseResponse(response);
        healthPill.textContent = data.status;
        healthPill.className = "status-pill ok";
      }} catch (error) {{
        healthPill.textContent = "offline";
        healthPill.className = "status-pill err";
      }}
    }}

    async function checkDrive() {{
      show("Checking Drive...");
      const response = await fetch("/api/v1/drive/status", {{ headers: headers() }});
      const data = await parseResponse(response);
      document.getElementById("sampleCount").textContent = data.input_folder.sample_count;
      document.getElementById("canList").textContent = data.input_folder.can_list ? "OK" : "NG";
      document.getElementById("canAdd").textContent = data.output_folder.can_add ? "OK" : "NG";
      const files = data.input_folder.sample_files || [];
      document.getElementById("fileList").innerHTML = files.length
        ? files.map(file => `<div class="file"><strong>${{file.name}}</strong><span>${{file.mimeType}}</span></div>`).join("")
        : `<div class="file"><strong>入力フォルダは空です</strong><span>PDF / 画像 / txt を追加</span></div>`;
      show(data);
    }}

    async function startBatch() {{
      show("Starting batch...");
      const form = new FormData();
      form.append("storage_type", "google_drive");
      const limit = document.getElementById("limitCount").value;
      if (limit) form.append("limit_count", limit);
      const chunkSize = document.getElementById("chunkSize").value;
      if (chunkSize) form.append("chunk_size", chunkSize);
      form.append("prompt_preset", document.getElementById("promptPreset").value);
      const custom = document.getElementById("customPrompt").value.trim();
      if (custom) form.append("custom_prompt", custom);
      const response = await fetch("/api/v1/document/batch-process", {{
        method: "POST",
        headers: headers(),
        body: form
      }});
      show(await parseResponse(response));
    }}

    function bind(id, fn) {{
      const el = document.getElementById(id);
      el.addEventListener("click", async () => {{
        el.disabled = true;
        try {{ await fn(); }}
        catch (error) {{ show(error); }}
        finally {{ el.disabled = false; }}
      }});
    }}

    bind("saveKeyBtn", async () => {{
      localStorage.setItem("pipelineDemoApiKey", apiKey());
      show("API key saved in this browser.");
    }});
    bind("checkDriveBtn", checkDrive);
    bind("startBatchBtn", startBatch);
    checkHealth();
  </script>
</body>
</html>"""
