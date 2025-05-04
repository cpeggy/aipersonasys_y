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
import time
from openai import RateLimitError  # 確保導入這個
import opencc
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import google.generativeai as genai

GEMINI_MODEL = "gemini-2.0-flash"
MAX_RETRIES = 5  # 最大重試次數
MIN_WAIT = 2  # 最小等待時間（秒）
MAX_WAIT = 60  # 最大等待時間（秒）

def clean_persona(persona):
    cleaned = {k: v for k, v in persona.items() if v and v != '...'}
    if 'suggested_learning_resources' in cleaned:
        cleaned['suggested_learning_resources'] = [
            {k: v for k, v in r.items() if v and v != '...'}
            for r in cleaned['suggested_learning_resources']
            if any(v and v != '...' for v in r.values())
        ]
    return cleaned

# 修改所有處理函數以傳遞 API Key
async def process_csv(csv_path, output_folder, api_key=None):
    with open(csv_path, 'rb') as f:
        encoding = chardet.detect(f.read(10000))['encoding']
    df = pd.read_csv(csv_path, encoding=encoding)
    full_text = df.to_string(index=False)

    estimated_tokens = len(full_text) / 2
    if estimated_tokens > 100000:
        raise ValueError("問卷資料太大，超過模型可以處理的範圍，請減少資料量。")

    print(f"CSV資料總長度：{len(full_text)} 字元，估算約 {int(estimated_tokens)} tokens")

    prompt = generate_prompt(full_text, is_csv=True)
    personas, messages = await _generate_personas(prompt, api_key)
    return _save_personas(personas, output_folder, "csv", messages)

async def process_csv2(csv_path, output_folder, api_key=None):
    """處理第二種類型的 CSV，使用不同的前綴來區分 persona ID"""
    try:
        # 嘗試使用不同的編碼方式讀取檔案
        encoding = None
        try:
            with open(csv_path, 'rb') as f:
                encoding_result = chardet.detect(f.read(10000))
                encoding = encoding_result['encoding']
                print(f"檢測到文件編碼：{encoding}，置信度：{encoding_result['confidence']}")
        except Exception as e:
            print(f"檢測編碼時出錯：{e}，將使用 utf-8")
            encoding = 'utf-8'
        
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
        except UnicodeDecodeError:
            print(f"使用 {encoding} 解碼失敗，嘗試 utf-8 編碼")
            df = pd.read_csv(csv_path, encoding='utf-8', errors='replace')
        
        full_text = df.to_string(index=False)

        estimated_tokens = len(full_text) / 2
        if estimated_tokens > 100000:
            raise ValueError("問卷資料太大，超過模型可以處理的範圍，請減少資料量。")

        print(f"CSV2資料總長度：{len(full_text)} 字元，估算約 {int(estimated_tokens)} tokens")

        prompt = generate_prompt(full_text, is_csv=True)
        
        # 使用改進的錯誤處理和重試機制
        retry_count = 0
        max_retries = 3
        
        while True:
            try:
                personas, messages = await _generate_personas(prompt, api_key)
                return _save_personas(personas, output_folder, "csv2", messages)
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"已達最大重試次數 ({max_retries})，放棄處理")
                    raise
                
                wait_time = min(30, 5 * retry_count)  # 逐漸增加等待時間，但最多等 30 秒
                print(f"處理時發生錯誤：{str(e)}。將在 {wait_time} 秒後重試 ({retry_count}/{max_retries})...")
                await asyncio.sleep(wait_time)
    
    except Exception as e:
        print(f"CSV2 處理過程中出現錯誤：{str(e)}")
        # 返回空結果以避免前端完全崩潰
        return "", "", "", []

async def process_md(md_paths, output_folder, api_key=None):
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
    personas, messages = await _generate_personas(prompt, api_key)
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

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=MIN_WAIT, max=MAX_WAIT),
    retry=retry_if_exception_type((RateLimitError, RuntimeError, asyncio.TimeoutError))
)
async def _generate_personas(prompt, api_key=None):
    """直接使用 Gemini API 生成 personas，不使用 autogen-agentchat"""
    try:
        # 使用傳入的 API Key 或從環境變數獲取
        if api_key:
            genai.configure(api_key=api_key)
        else:
            api_key_env = os.getenv("Gemini_api")
            if api_key_env:
                genai.configure(api_key=api_key_env)
            else:
                raise ValueError("缺少 Google API Key")
        
        # 設置較長的超時時間
        timeout = 60  # 60 秒超時
        
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        # 使用超時控制
        async def run_with_timeout():
            # 由於 genai 庫沒有異步支持，我們在執行緒池中執行同步 API 呼叫
            loop = asyncio.get_event_loop()
            
            def sync_call():
                try:
                    response = model.generate_content(prompt)
                    return response.text
                except Exception as e:
                    print(f"Gemini API 呼叫錯誤: {e}")
                    raise
            
            response_text = await loop.run_in_executor(None, sync_call)
            return response_text
        
        # 設置超時
        try:
            response_text = await asyncio.wait_for(run_with_timeout(), timeout=timeout)
        except asyncio.TimeoutError:
            print(f"API 呼叫超時 ({timeout} 秒)")
            raise
        
        # 解析回應中的 JSON 格式 persona 數據
        personas = []
        messages = [{"content": prompt, "role": "user"}, {"content": response_text, "role": "assistant"}]
        
        # 尋找 JSON 區塊
        blocks = re.findall(r"```json\n(.*?)\n```", response_text, re.DOTALL)
        for block in blocks:
            try:
                obj = json.loads(block)
                if isinstance(obj, dict):
                    personas.append(obj)
                elif isinstance(obj, list):
                    personas.extend(obj)
            except json.JSONDecodeError as json_err:
                print(f"JSON 解析錯誤: {json_err}")
                # 嘗試修正 JSON 並再次解析
                try:
                    fixed_block = block.replace("'", '"').replace("\\", "\\\\")
                    obj = json.loads(fixed_block)
                    if isinstance(obj, dict):
                        personas.append(obj)
                    elif isinstance(obj, list):
                        personas.extend(obj)
                except Exception as fix_err:
                    print(f"修正 JSON 失敗: {fix_err}，略過此區塊")
        
        # 檢查是否找到有效的 personas
        if personas:
            return personas, messages
        else:
            print("API 返回無效: 未找到有效的 persona 資料")
            raise ValueError("未能生成有效的 persona 資料")
            
    except Exception as e:
        error_str = str(e)
        
        # 檢查是否為速率限制錯誤 (429 或 503)
        if "429" in error_str or "RateLimitError" in error_str or "overloaded" in error_str:
            print(f"遇到 API 速率限制或過載錯誤: {error_str}")
            # 重試裝飾器會處理重試
            raise
        else:
            # 其他錯誤，讓重試裝飾器嘗試重試
            print(f"發生其他錯誤: {error_str}")
            raise
        
async def process_large_csv(csv_path, output_folder, batch_size=BATCH_SIZE, api_key=None):
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
        
        retry_count = 0
        max_chunk_retries = 2  # 每個批次最多重試次數
        
        while retry_count <= max_chunk_retries:
            try:
                # 處理此批次
                chunk_personas, chunk_messages = await _generate_personas(chunk_prompt, api_key)
                
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
                
                # 成功處理，跳出重試循環
                break
                
            except Exception as e:
                retry_count += 1
                print(f"批次 {i+1} 處理出錯: {e}")
                
                if retry_count <= max_chunk_retries:
                    wait_time = min(60, 15 * retry_count)  # 逐漸增加等待時間
                    print(f"將在 {wait_time} 秒後重試批次 {i+1} ({retry_count}/{max_chunk_retries})...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"批次 {i+1} 已達最大重試次數，繼續處理下一批次")
                    # 記錄錯誤但繼續處理下一個批次
    
    # 如果至少有一些 personas 成功生成，則保存它們
    if all_personas:
        print(f"全部批次處理完成，共收集到 {len(all_personas)} 個 personas")
        return _save_personas(all_personas, output_folder, "csv", all_messages)
    else:
        raise ValueError("所有批次處理都失敗，未能生成任何 persona")

async def process_large_csv2(csv_path, output_folder, batch_size=15000, api_key=None):
    """處理大型 CSV2 文件，使用改進的錯誤處理策略"""
    try:
        # 嘗試使用不同的編碼方式讀取檔案
        encoding = None
        try:
            with open(csv_path, 'rb') as f:
                encoding_result = chardet.detect(f.read(10000))
                encoding = encoding_result['encoding']
                print(f"檢測到文件編碼：{encoding}，置信度：{encoding_result['confidence']}")
        except Exception as e:
            print(f"檢測編碼時出錯：{e}，將使用 utf-8")
            encoding = 'utf-8'
        
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
        except UnicodeDecodeError:
            print(f"使用 {encoding} 解碼失敗，嘗試 utf-8 編碼")
            df = pd.read_csv(csv_path, encoding='utf-8', errors='replace')
        
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
            
            # 增加每個批次的重試次數和更長的等待時間
            retry_count = 0
            max_chunk_retries = 3
            
            while retry_count <= max_chunk_retries:
                try:
                    # 處理此批次
                    chunk_personas, chunk_messages = await _generate_personas(chunk_prompt, api_key)
                    
                    # 添加批次信息到每個 persona
                    for p in chunk_personas:
                        p['batch_info'] = f"Batch {i+1}/{len(chunks)}"
                    
                    # 收集結果
                    all_personas.extend(chunk_personas)
                    all_messages.extend(chunk_messages)
                    
                    # 批次之間等待較長時間，避免 API 限制
                    print(f"批次 {i+1} 完成，生成了 {len(chunk_personas)} 個 personas")
                    if i < len(chunks) - 1:  # 如果不是最後一個批次
                        wait_time = 20  # 增加到 20 秒
                        print(f"等待 {wait_time} 秒後處理下一批次...")
                        await asyncio.sleep(wait_time)
                    
                    # 成功處理，跳出重試循環
                    break
                        
                except Exception as e:
                    retry_count += 1
                    print(f"批次 {i+1} 處理出錯: {e}")
                    
                    if retry_count <= max_chunk_retries:
                        # 使用指數退避策略
                        wait_time = min(120, 20 * (2 ** (retry_count - 1)))
                        print(f"將在 {wait_time} 秒後重試批次 {i+1} ({retry_count}/{max_chunk_retries})...")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"批次 {i+1} 已達最大重試次數，繼續處理下一批次")
        
        # 如果至少有一些 personas 成功生成，則保存它們
        if all_personas:
            print(f"全部批次處理完成，共收集到 {len(all_personas)} 個 personas")
            return _save_personas(all_personas, output_folder, "csv2", all_messages)
        else:
            # 在所有批次都失敗的情況下，返回空數據而不是拋出異常
            print("所有批次處理都失敗，返回空數據")
            return "", "", "", []
            
    except Exception as e:
        print(f"CSV2 大檔案處理過程中出現錯誤：{str(e)}")
        # 返回空結果以避免前端完全崩潰
        return "", "", "", []
    
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

import opencc

def convert_to_traditional(text):
    """将简体中文文本转换为繁体中文"""
    if not text or not isinstance(text, str):
        return text
    converter = opencc.OpenCC('s2t')  # 简体到繁体转换器
    return converter.convert(text)

# 修改clean_persona函数以添加简繁转换
def clean_persona(persona):
    # 首先进行原有的清理
    cleaned = {k: v for k, v in persona.items() if v and v != '...'}
    
    # 对每个字符串字段进行简繁转换
    for key, value in cleaned.items():
        if isinstance(value, str):
            cleaned[key] = convert_to_traditional(value)
        elif key == 'suggested_learning_resources' and isinstance(value, list):
            cleaned[key] = []
            for resource in value:
                if isinstance(resource, dict):
                    converted_resource = {}
                    for k, v in resource.items():
                        if isinstance(v, str) and v and v != '...':
                            converted_resource[k] = convert_to_traditional(v)
                        elif v and v != '...':
                            converted_resource[k] = v
                    if converted_resource:
                        cleaned[key].append(converted_resource)
    
    return cleaned