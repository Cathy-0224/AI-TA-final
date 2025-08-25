from flask import Flask, request, jsonify, render_template, redirect, url_for
from google import genai
from google.genai import types
from google.genai.errors import ClientError
import time
import re

# 初始化 Gemini 客戶端
client = genai.Client()

# 全域儲存歷史設定（可改成資料庫或檔案）
history_list = []

# 安全呼叫 Gemini 函式（含重試機制）
def safe_generate_content(prompt, max_retries=3, sleep_seconds=5):
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite-preview-06-17",
                contents=types.Content(role="user", parts=[types.Part(text=prompt)]),
                config=types.GenerateContentConfig()
            )
            return response.candidates[0].content.parts[0].text.strip()
        except ClientError as e:
            if "RESOURCE_EXHAUSTED" in str(e):
                time.sleep(sleep_seconds)
            else:
                raise e
    raise Exception("已超過 Gemini 重試次數，請稍後再試")

# 判斷是否為列點項目
def is_bullet_point(line: str) -> bool:
    return bool(re.match(r'^\s*([-•*‧]|\d+\.|[一二三四五六七八九十]+、)', line))

# 清理列點文字：移除開頭符號與所有 '*'，並 trim
def clean_point(line: str) -> str:
    text = re.sub(r'^\s*[-•*‧]\s*', '', line)
    return text.replace('*', '').strip()

def summarize_by_key(text: str, language="繁體中文"):
    prompt = (
        f"任務: 依據整段逐字稿內容，列點摘要其主要重點，不需開場與結語。"
        f"摘要方式: {language} 列點。逐字稿內容:{text}"
    )
    res = safe_generate_content(prompt)
    return {
        '整體': [clean_point(line) for line in res.splitlines() if is_bullet_point(line)]
    }

def generate_suggestions(text: str, role: str, context: str, focus: str, custom: str, language="繁體中文"):
    prompt = (
        f"角色:{role} ，任務: {context}，逐字稿內容:{text}，依據{focus}來生成{language}建議 "
        f"格式: {custom}"
    )
    res = safe_generate_content(prompt)
    return res.replace('*', '').strip()

# 路由：設定頁面
app = Flask(__name__)
@app.route('/')
def show_settings():
    # 顯示參數設定表單與歷史清單
    return render_template('index.html', history=history_list)

# 路由：儲存設定並跳轉
@app.route('/settings', methods=['POST'])
def save_settings():
    role = request.form.get('role')
    context = request.form.get('context')
    focus = request.form.get('focus')
    custom = request.form.get('custom')
    settings = { 'role': role, 'context': context, 'focus': focus, 'custom': custom }
    # 新增到最前，並限10筆
    history_list.insert(0, settings)
    if len(history_list) > 10:
        history_list.pop()
    # 重定向到語音助理，並帶參數
    return redirect(url_for('assistant', **settings))

# 路由：語音辨識助理頁
@app.route('/assistant')
def assistant():
    # 從查詢參數讀取設定（不再建立 base_prompt）
    role = request.args.get('role')
    context = request.args.get('context')
    focus = request.args.get('focus')
    custom = request.args.get('custom')
    return render_template('index2.html', role=role, context=context,
                           focus=focus, custom=custom)

# 路由：語音摘要與建議 API
@app.route('/summarize', methods=['POST'])
def summarize_route():
    # 1) 先嘗試解析 JSON body（若前端有傳 Content-Type: application/json）
    data = request.get_json(silent=True)
    if data is None:
        data = {}

    # helper: 若欄位存在於 JSON（即使是空字串）就使用 JSON 的值，否則 fallback 到 query string
    def get_param(name, default=''):
        if name in data:
            val = data[name]
            return '' if val is None else str(val)
        return request.args.get(name, default)

    text = get_param('text', '').strip()
    role = get_param('role', '')
    context = get_param('context', '')
    focus = get_param('focus', '')
    custom = get_param('custom', '')

    # 基本驗證：text 是必要欄位
    if not text:
        return jsonify({'error': 'missing parameter: text', 'summary': {}, 'suggestion': ''}), 400

    # 簡單的長度限制，避免把過大的輸入直接塞到 LLM
    MAX_TEXT = 20000
    MAX_CUSTOM = 1000
    if len(text) > MAX_TEXT:
        return jsonify({'error': 'text too long', 'summary': {}, 'suggestion': ''}), 400
    if len(custom) > MAX_CUSTOM:
        custom = custom[:MAX_CUSTOM]

    summary = summarize_by_key(text)
    suggestion = generate_suggestions(text, role, context, focus, custom)
    return jsonify({'summary': summary, 'suggestion': suggestion})

# 啟動
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
