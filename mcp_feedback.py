# mcp_feedback.py
import os
import re
import json
import asyncio
import base64
import traceback
from io import BytesIO
import google.generativeai as genai
from openai import OpenAIError, ChatCompletion
from google.api_core.exceptions import GoogleAPICallError, RetryError
from google.api_core.exceptions import ResourceExhausted
from autogen_agentchat.messages import TextMessage
import plotly.graph_objects as go

GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_API_KEY = os.getenv("Gemini_api")  # 注意這裡是正確讀.env

def run_mcp_feedback(selected_personas, marketing_copy):
    """
    主程式：對多個 persona 執行回饋，
    並回傳 (feedback_list, avg_score, base64_chart_png)
    """
    feedback_data = []
    scores = []

    for persona in selected_personas:
        # 不再需要從文件加載 persona
        prompt = generate_prompt(persona, marketing_copy)

        # 使用 sync_call_gemini_model 函數
        try:
            response_text = sync_call_gemini_model(prompt)
        except Exception as e:
            print(f"Gemini API 呼叫失敗: {e}")
            response_text = "呼叫失敗"

        parsed = parse_feedback_response(response_text, persona_id=persona.get('persona_id', 'Unknown'))
        feedback_data.append(parsed)
        scores.append(parsed.get('score', 0))

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
=== 學習動機 ===
{persona.get('motivation', '無')}
=== 面臨挑戰 ===
{persona.get('challenges', '無')}
=== 學習目標 ===
{persona.get('learning_goals', '無')}
=== 偏好的學習方式 ===
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
  "score": 7,
  "reasons_to_buy": ["...", "..."],
  "reasons_not_to_buy": ["..."]
}}
"""


# 改為同步函數，供 call_gemini_model 使用
def sync_call_gemini_model(prompt):
    """同步呼叫 Gemini API"""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini API 呼叫失敗: {e}")
        return "呼叫失敗"


# 添加異步函數版本
async def async_call_gemini_model(prompt, persona_id):
    """異步呼叫 Gemini API"""
    try:
        # 使用執行緒池執行同步 API 呼叫
        loop = asyncio.get_event_loop()
        response_text = await loop.run_in_executor(None, lambda: sync_call_gemini_model(prompt))
        
        # 解析回應
        return parse_feedback_response(response_text, persona_id)
    except Exception as e:
        print(f"Gemini API 異步呼叫失敗: {e}")
        return None


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
            return {
                "persona_id": persona_id,
                "score": 5,
                "reasons_to_buy": [],
                "reasons_not_to_buy": [],
                "detail_feedback": response_text.strip()
            }
    except Exception as e:
        print(f"解析失敗: {e}")
        return {
            "persona_id": persona_id,
            "score": 5,
            "reasons_to_buy": [],
            "reasons_not_to_buy": [],
            "detail_feedback": response_text.strip()
        }


def generate_chart(feedback_data, avg_score):
    """生成評分圖表，返回 base64 編碼的圖片"""
    if not feedback_data:
        return ""
    
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
    
    # 配置圖表
    fig.update_layout(
        title="各 Persona 購買意願評分",
        yaxis_title="評分 (1-10)",
        yaxis_range=[0, 10],
        template="plotly_white",
    )
    
    # 轉為 base64 字串
    img_bytes = fig.to_image(format="png", width=800, height=400)
    return base64.b64encode(img_bytes).decode('utf-8')

# ---------------
# 可以 export 的函式
# ---------------

__all__ = ['run_mcp_feedback']