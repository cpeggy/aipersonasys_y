# mcp_feedback.py
import os
import re
import json
import asyncio
import base64
import traceback
from io import BytesIO
import google.generativeai as genai
from openai import OpenAIError
from google.api_core.exceptions import GoogleAPICallError, RetryError
from google.api_core.exceptions import ResourceExhausted
import plotly.graph_objects as go
import time

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_KEY = os.getenv("Gemini_api")  # 注意這裡是正確讀.env

# 主程式：對多個 persona 執行回饋，並回傳 (feedback_list, avg_score, base64_chart_png)
def run_mcp_feedback(selected_personas, marketing_copy):
    """主程式：對多個 persona 執行回饋，並回傳 (feedback_data, avg_score, base64_chart_png)"""
    feedback_data = []
    scores = []
    
    # 將 personas 分成更小的批次，每批最多 2 個
    batch_size = 2
    persona_batches = [
        selected_personas[i:i+batch_size] 
        for i in range(0, len(selected_personas), batch_size)
    ]
    
    for batch_index, batch in enumerate(persona_batches):
        print(f"處理批次 {batch_index+1}/{len(persona_batches)}, {len(batch)} 個 Personas")
        
        # 處理每個批次中的 personas
        batch_results = []
        for persona in batch:
            try:
                prompt = generate_prompt(persona, marketing_copy)
                response_text = sync_call_gemini_model(prompt)
                parsed = parse_feedback_response(response_text, persona_id=persona.get('persona_id', 'Unknown'))
                batch_results.append(parsed)
                print(f"  成功評估 Persona {persona.get('persona_id')}, 得分: {parsed.get('score', 0)}")
                
                # 每個請求之間等待 3 秒，避免單一批次內的速率限制
                time.sleep(3)
            except Exception as e:
                print(f"  評估 Persona {persona.get('persona_id')} 失敗: {e}")
                # 添加失敗記錄
                batch_results.append({
                    'persona_id': persona.get('persona_id', 'Unknown'),
                    'score': 0,
                    'reasons_to_buy': ['評估失敗'],
                    'reasons_not_to_buy': ['API 速率限制'],
                    'detail_feedback': f'評估失敗: {str(e)}'
                })
        
        # 將批次結果合併到總結果
        feedback_data.extend(batch_results)
        scores.extend([item.get('score', 0) for item in batch_results if item.get('score', 0) > 0])
        
        # 批次之間等待較長時間以避免 API 限制
        if batch_index < len(persona_batches) - 1:
            wait_time = 20  # 增加到 20 秒
            print(f"等待 {wait_time} 秒後處理下一批次...")
            time.sleep(wait_time)
    
    # 確保至少有一個有效分數
    if not scores:
        scores = [0]
        
    avg_score = sum(scores) / len(scores) if scores else 0.0
    chart_png = generate_chart(feedback_data, avg_score)
    return feedback_data, avg_score, chart_png

def load_persona(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_prompt(persona, marketing_copy):
    return f"""
你現在是一位 Persona：
=== Persona 描述 ===
{persona.get('description', '無')}
學習動機：
{persona.get('motivation', '無')}
面臨挑戰：
{persona.get('challenges', '無')}
學習目標：
{persona.get('learning_goals', '無')}
偏好的學習方式：
{persona.get('preferred_learning_methods', '無')}

請針對以下行銷文案提供詳細回饋：
=== 行銷文案 ===
{marketing_copy}

請依照以下格式回答：
1. 購買意願評分（1-10）：
2. 購買理由（條列式列出 1.2.3.）
3. 不購買理由（條列式列出 1.2.3.）
4. 詳細說明：

結果請用純 JSON 輸出，例如：
```json
{{
  "score": ?,
  "reasons_to_buy": ["...", "..."],
  "reasons_not_to_buy": ["..."]
}}
"""

# 改為同步函數，供 call_gemini_model 使用
def sync_call_gemini_model(prompt, max_retries=3, retry_delay=5):
    """同步呼叫 Gemini API，帶有重試機制"""
    retries = 0
    while retries < max_retries:
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            retry_seconds = get_retry_delay(str(e))
            retries += 1
            if retries < max_retries:
                print(f"Gemini API 呼叫失敗 (嘗試 {retries}/{max_retries}): {e}")
                print(f"等待 {retry_seconds} 秒後重試...")
                time.sleep(retry_seconds)
            else:
                print(f"Gemini API 呼叫失敗，已達最大重試次數: {e}")
                raise  # 重新拋出異常，讓調用者知道失敗了
    return None  # 這行實際上不會被執行到，因為最後一次失敗會拋出異常

def get_retry_delay(error_msg):
    """從錯誤消息中提取建議的重試延遲，並加 1 秒作為額外緩衝"""
    # 嘗試尋找 'retry_delay { seconds: XX }' 模式
    match = re.search(r'retry_delay\s*{\s*seconds:\s*(\d+)\s*}', error_msg)
    if match:
        # 從匹配中提取數字，並加 1 秒作為緩衝
        return int(match.group(1)) + 1  # 將建議的等待時間加 1 秒
    else:
        # 默認等待時間
        return 17  # 如果找不到建議等待時間，使用 15 秒作為安全值

def parse_feedback_response(response_text, persona_id):
    """解析 Gemini 回應的 JSON"""
    try:
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if match:
            feedback_json = json.loads(match.group(0))
            return {
                "persona_id": persona_id,
                "score": feedback_json.get("score", 5),
                "reasons_to_buy": feedback_json.get("reasons_to_buy", []),
                "reasons_not_to_buy": feedback_json.get("reasons_not_to_buy", []),
                "detail_feedback": response_text.strip()
            }
        else:
            print(f"找不到 JSON 區塊，原始回應: {response_text}")
            
            # 檢查是否是 API 錯誤或空回應
            if "呼叫失敗" in response_text or not response_text.strip():
                raise ValueError("API 呼叫失敗，無法取得評估結果")
                
            # 如果回應存在但格式不符，生成一個基本的分數
            return {
                "persona_id": persona_id,
                "score": 5,  # 預設分數
                "reasons_to_buy": ["無法解析回應"],
                "reasons_not_to_buy": ["API 回應格式不符"],
                "detail_feedback": response_text.strip()
            }
    except Exception as e:
        print(f"解析失敗: {e}")
        raise  # 重新拋出異常，讓調用者能夠處理

# 修改 generate_chart 函數
def generate_chart(feedback_data, avg_score):
    """生成評分圖表，返回 base64 編碼的圖片"""
    if not feedback_data:
        return ""
    
    # 排序 feedback_data 以確保顯示順序一致
    feedback_data = sorted(feedback_data, key=lambda x: str(x['persona_id']))
    
    # 準備繪圖資料
    labels = [f"Persona {item['persona_id']}" for item in feedback_data]
    scores = [item['score'] for item in feedback_data]
    
    # 創建長條圖
    fig = go.Figure(go.Bar(
        x=labels,
        y=scores,
        marker_color=['green' if s >= 8 else 'blue' if s >= 6 else 'orange' if s >= 4 else 'red' for s in scores],
        text=scores,
        textposition='auto',
    ))
    
    # 添加平均線
    fig.add_shape(
        type="line",
        x0=-0.5,
        x1=len(labels) - 0.5,
        y0=avg_score,
        y1=avg_score,
        line=dict(color="red", width=2, dash="dash"),
    )
    
    # 添加註解
    fig.add_annotation(
        x=len(labels) - 1,
        y=avg_score,
        text=f"平均: {avg_score:.1f}",
        showarrow=True,
        arrowhead=1,
    )
    
    # 配置圖表 - 確保所有數值都能顯示
    fig.update_layout(
        title="各 Persona 購買意願評分",
        yaxis_title="評分 (1-10)",
        yaxis_range=[0, 10],
        template="plotly_white",
        width=1000,  # 設置寬度以確保所有標籤可見
        height=800,  # 增加高度
        margin=dict(l=50, r=50, t=50, b=150),  # 增加底部邊距以顯示標籤
    )
    
    # 調整 x 軸標籤方向，避免重疊
    fig.update_xaxes(tickangle=45)
    
    # 轉為 base64 字串
    img_bytes = fig.to_image(format="png", width=800, height=500)
    return base64.b64encode(img_bytes).decode('utf-8')

# ---------------
# 可以 export 的函式
# ---------------

__all__ = ['run_mcp_feedback']