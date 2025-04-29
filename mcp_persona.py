import os
import json
import re
import asyncio
import pandas as pd
import chardet
import zipfile
import io
import base64
import plotly.graph_objects as go
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.conditions import TextMentionTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient
import time
from openai import RateLimitError  # 確保導入這個

GEMINI_MODEL = "gemini-2.0-flash"

def clean_persona(persona):
    cleaned = {k: v for k, v in persona.items() if v and v != '...'}
    if 'suggested_learning_resources' in cleaned:
        cleaned['suggested_learning_resources'] = [
            {k: v for k, v in r.items() if v and v != '...'}
            for r in cleaned['suggested_learning_resources']
            if any(v and v != '...' for v in r.values())
        ]
    return cleaned

async def process_csv(csv_path, output_folder):
    with open(csv_path, 'rb') as f:
        encoding = chardet.detect(f.read(10000))['encoding']
    df = pd.read_csv(csv_path, encoding=encoding)
    full_text = df.to_string(index=False)

    estimated_tokens = len(full_text) / 2
    if estimated_tokens > 100000:
        raise ValueError("問卷資料太大，超過模型可以處理的範圍，請減少資料量。")

    print(f"CSV資料總長度：{len(full_text)} 字元，估算約 {int(estimated_tokens)} tokens")

    prompt = generate_prompt(full_text, is_csv=True)
    personas, messages = await _generate_personas(prompt)
    return _save_personas(personas, output_folder, "csv", messages)

async def process_csv2(csv_path, output_folder):
    """處理第二種類型的 CSV，使用不同的前綴來區分 persona ID"""
    with open(csv_path, 'rb') as f:
        encoding = chardet.detect(f.read(10000))['encoding']
    df = pd.read_csv(csv_path, encoding=encoding)
    full_text = df.to_string(index=False)

    estimated_tokens = len(full_text) / 2
    if estimated_tokens > 100000:
        raise ValueError("問卷資料太大，超過模型可以處理的範圍，請減少資料量。")

    print(f"CSV2資料總長度：{len(full_text)} 字元，估算約 {int(estimated_tokens)} tokens")

    prompt = generate_prompt(full_text, is_csv=True)
    personas, messages = await _generate_personas(prompt)
    return _save_personas(personas, output_folder, "csv2", messages)

async def process_md(md_paths, output_folder):
    contents = []
    for path in md_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                contents.append(f.read())
        except UnicodeDecodeError:
            with open(path, 'rb') as f:
                raw = f.read()
                encoding = chardet.detect(raw)['encoding']
                contents.append(raw.decode(encoding, errors='replace'))

    full_text = "\n\n=== 分隔線 ===\n\n".join(contents)

    estimated_tokens = len(full_text) / 2

    print(f"MD資料總長度：{len(full_text)} 字元，估算約 {int(estimated_tokens)} tokens")

    prompt = generate_prompt(full_text, is_csv=False)
    personas, messages = await _generate_personas(prompt)
    return _save_personas(personas, output_folder, "md", messages)

def generate_prompt(full_text, is_csv=True):
    """根據是問卷還是訪談，自動生成 prompt"""
    source_type = "問卷" if is_csv else "訪談"
    return (
        f"這是{source_type}資料：\n{full_text}\n\n"
        "請根據以上資料，統整分析，生成完整的課程受眾 persona 概觀，每個 persona 包含以下欄位：\n"
        "- persona_id（1開始編號）\n"
        "- description（受眾整體概括描述）\n"
        "- motivation（學習動機）\n"
        "- challenges（面臨挑戰與痛點）\n"
        "- learning_goals（學習目標）\n"
        "- preferred_learning_methods（偏好學習方式）\n"
        "- suggested_learning_resources（推薦學習資源，包含 feature_name, description, justification）\n\n"
        "請用 JSON 格式輸出，範例如下：\n"
        "```json\n"
        "{\n"
        '  "persona_id": "1",\n'
        '  "description": "...",\n'
        '  "motivation": "...",\n'
        '  "challenges": "...",\n'
        '  "learning_goals": "...",\n'
        '  "preferred_learning_methods": "...",\n'
        '  "suggested_learning_resources": [\n'
        "    {\n"
        '      "feature_name": "...",\n'
        '      "description": "...",\n'
        '      "justification": "..." \n'
        "    }\n"
        "  ]\n"
        "}\n"
        "```\n"
        "請確保只輸出上述 JSON，不要有其他文字說明。"
    )

# 在文件頂部添加配置參數
BATCH_SIZE = 15000          # 每批大約字符數
BATCH_WAIT_TIME = 5         # 批次間等待時間（秒）
LARGE_FILE_THRESHOLD = 40000  # 大文件閾值（tokens）

async def process_large_csv(csv_path, output_folder, batch_size=BATCH_SIZE):
    """處理大型 CSV 文件，分批發送到 API"""
    with open(csv_path, 'rb') as f:
        encoding = chardet.detect(f.read(10000))['encoding']
    
    df = pd.read_csv(csv_path, encoding=encoding)
    full_text = df.to_string(index=False)
    
    # 計算 token 數量
    estimated_tokens = len(full_text) / 2
    print(f"大型CSV資料總長度：{len(full_text)} 字元，估算約 {int(estimated_tokens)} tokens")
    print(f"將進行分批處理，每批約 {batch_size/2} tokens")
    
    # 分割文本為多個較小的部分
    chunks = []
    for i in range(0, len(full_text), batch_size):
        chunks.append(full_text[i:i + batch_size])
    
    print(f"共分割為 {len(chunks)} 個批次")
    
    all_personas = []
    all_messages = []
    
    for i, chunk in enumerate(chunks):
        print(f"處理第 {i+1}/{len(chunks)} 批次，大小約 {len(chunk) / 2} tokens")
        
        # 為每個批次生成專屬提示
        chunk_prompt = generate_prompt(chunk, is_csv=True)
        
        try:
            # 處理此批次
            chunk_personas, chunk_messages = await _generate_personas(chunk_prompt)
            
            # 添加批次信息到每個 persona
            for p in chunk_personas:
                p['batch_info'] = f"Batch {i+1}/{len(chunks)}"
            
            # 收集結果
            all_personas.extend(chunk_personas)
            all_messages.extend(chunk_messages)
            
            # 批次之間等待短暫時間，避免過度頻繁的 API 調用
            print(f"批次 {i+1} 完成，生成了 {len(chunk_personas)} 個 personas")
            if i < len(chunks) - 1:  # 如果不是最後一個批次
                wait_time = 5  # 等待 5 秒
                print(f"等待 {wait_time} 秒後處理下一批次...")
                await asyncio.sleep(wait_time)
                
        except Exception as e:
            print(f"批次 {i+1} 處理出錯: {e}")
            # 記錄錯誤但繼續處理下一個批次
    
    # 如果至少有一些 personas 成功生成，則保存它們
    if all_personas:
        print(f"全部批次處理完成，共收集到 {len(all_personas)} 個 personas")
        return _save_personas(all_personas, output_folder, "csv", all_messages)
    else:
        raise ValueError("所有批次處理都失敗，未能生成任何 persona")

# 對於 CSV2，添加相同的批次處理函數
async def process_large_csv2(csv_path, output_folder, batch_size=15000):
    """處理大型 CSV2 文件，分批發送到 API"""
    with open(csv_path, 'rb') as f:
        encoding = chardet.detect(f.read(10000))['encoding']
    
    df = pd.read_csv(csv_path, encoding=encoding)
    full_text = df.to_string(index=False)
    
    # 計算 token 數量
    estimated_tokens = len(full_text) / 2
    print(f"大型CSV2資料總長度：{len(full_text)} 字元，估算約 {int(estimated_tokens)} tokens")
    print(f"將進行分批處理，每批約 {batch_size/2} tokens")
    
    # 分割文本為多個較小的部分
    chunks = []
    for i in range(0, len(full_text), batch_size):
        chunks.append(full_text[i:i + batch_size])
    
    print(f"共分割為 {len(chunks)} 個批次")
    
    all_personas = []
    all_messages = []
    
    for i, chunk in enumerate(chunks):
        print(f"處理第 {i+1}/{len(chunks)} 批次，大小約 {len(chunk) / 2} tokens")
        
        # 為每個批次生成專屬提示
        chunk_prompt = generate_prompt(chunk, is_csv=True)
        
        try:
            # 處理此批次
            chunk_personas, chunk_messages = await _generate_personas(chunk_prompt)
            
            # 添加批次信息到每個 persona
            for p in chunk_personas:
                p['batch_info'] = f"Batch {i+1}/{len(chunks)}"
            
            # 收集結果
            all_personas.extend(chunk_personas)
            all_messages.extend(chunk_messages)
            
            # 批次之間等待短暫時間，避免過度頻繁的 API 調用
            print(f"批次 {i+1} 完成，生成了 {len(chunk_personas)} 個 personas")
            if i < len(chunks) - 1:  # 如果不是最後一個批次
                wait_time = 5  # 等待 5 秒
                print(f"等待 {wait_time} 秒後處理下一批次...")
                await asyncio.sleep(wait_time)
                
        except Exception as e:
            print(f"批次 {i+1} 處理出錯: {e}")
            # 記錄錯誤但繼續處理下一個批次
    
    # 如果至少有一些 personas 成功生成，則保存它們
    if all_personas:
        print(f"全部批次處理完成，共收集到 {len(all_personas)} 個 personas")
        return _save_personas(all_personas, output_folder, "csv2", all_messages)
    else:
        raise ValueError("所有批次處理都失敗，未能生成任何 persona")
    
    
async def _generate_personas(prompt):
    """具有更強大重試機制的 persona 生成函數"""
    max_retries = 5
    retry_count = 0
    
    while True:
        try:
            model_client = OpenAIChatCompletionClient(model=GEMINI_MODEL, api_key=os.getenv("Gemini_api"))
            chat = RoundRobinGroupChat([AssistantAgent("gen", model_client)], 
                                       termination_condition=TextMentionTermination("TERMINATE"))

            personas = []
            messages = []

            async for event in chat.run_stream(task=prompt):
                if isinstance(event, TextMessage):
                    messages.append({
                        "source": event.source,
                        "content": event.content,
                        "type": event.type,
                        "prompt_tokens": event.models_usage.prompt_tokens if event.models_usage else None,
                        "completion_tokens": event.models_usage.completion_tokens if event.models_usage else None
                    })
                    blocks = re.findall(r"```json\n(.*?)\n```", event.content, re.DOTALL)
                    for block in blocks:
                        try:
                            obj = json.loads(block)
                            if isinstance(obj, dict):
                                personas.append(obj)
                            elif isinstance(obj, list):
                                personas.extend(obj)
                        except:
                            pass
            
            # 成功完成，返回結果
            return personas, messages
            
        except Exception as e:
            error_str = str(e)
            
            # 檢查是否為速率限制錯誤 (429)
            if "429" in error_str and "RateLimitError" in error_str:
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"已重試 {max_retries} 次但仍然失敗，放棄重試。")
                    raise
                
                # 從錯誤信息中提取建議等待時間 - 使用多種模式嘗試匹配
                retry_match = re.search(r"'retryDelay':\s*'(\d+)s'", error_str)
                if not retry_match:
                    retry_match = re.search(r'"retryDelay":\s*"(\d+)s"', error_str)
                if not retry_match:
                    retry_match = re.search(r'retryDelay["\']:\s*["\'](\d+)s["\']', error_str)

                wait_time = int(retry_match.group(1)) + 1 if retry_match else 50
                                
                print(f"{retry_count}/{max_retries} - 遇到速率限制，等待 {wait_time} 秒後重試...")
                await asyncio.sleep(wait_time)
                continue
            else:
                # 其他錯誤，直接拋出
                print(f"發生非速率限制錯誤: {e}")
                raise

def _save_personas(personas, output_folder, prefix, messages):
    """保存處理後的 personas 到檔案系統並返回路徑"""
    # 確保輸出目錄存在
    out_dir = os.path.join(output_folder, "personas", prefix)
    os.makedirs(out_dir, exist_ok=True)

    # 清理 persona 資料
    cleaned_personas = [clean_persona(p) for p in personas if len(clean_persona(p)) > 1]
    
    # 如果沒有有效 persona，返回空結果
    if not cleaned_personas:
        print(f"警告: 沒有找到有效的 personas")
        return "", "", "", []

    # 為每個 persona 設定正確 ID 並保存到獨立檔案
    for p in cleaned_personas:
        pid = p.get("persona_id", "unknown")
        # 確保 ID 有正確的前綴
        if not str(pid).startswith(f"{prefix}_"):
            p["persona_id"] = f"{prefix}_{pid}"
            
        # 保存個別 persona 檔案
        persona_file = os.path.join(out_dir, f"PERSONA-{p['persona_id']}.json")
        with open(persona_file, 'w', encoding='utf-8') as f:
            json.dump(p, f, ensure_ascii=False, indent=4)
        print(f"保存 persona 到 {persona_file}")

    # 合併所有 personas 成一個 json
    all_personas_path = os.path.join(output_folder, "personas", f"{prefix}_personas.json")
    with open(all_personas_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_personas, f, ensure_ascii=False, indent=4)
    print(f"合併 personas 到 {all_personas_path}")

    # 壓縮成 zip
    zip_path = os.path.join(output_folder, f"{prefix}_personas.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(out_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, out_dir)
                zipf.write(file_path, arcname)
    print(f"壓縮 personas 到 {zip_path}")

    # 保存對話紀錄
    output_csv_path = os.path.join(output_folder, f"all_{prefix}_conve_log.csv")
    pd.DataFrame(messages).to_csv(output_csv_path, index=False, encoding='utf-8-sig')
    print(f"保存對話紀錄到 {output_csv_path}")

    print(f"全部處理完成，共產生 {len(cleaned_personas)} 個 personas")
    return output_csv_path, zip_path, all_personas_path, cleaned_personas