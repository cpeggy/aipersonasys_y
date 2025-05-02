import os
import asyncio
import json
import datetime
import traceback
from flask import Flask, request, jsonify, render_template, send_file
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from mcp_feedback import run_mcp_feedback
from mcp_persona import process_csv, process_csv2, process_md
import zipfile

from flask import Flask
app = Flask(__name__)


# 初始化 Flask
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# 建立必要資料夾
for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER'], os.path.join(app.config['OUTPUT_FOLDER'], "personas")]:
    os.makedirs(folder, exist_ok=True)

# 載入 .env
load_dotenv()

# ============ 路由設定 ============

@app.route('/')
def index():
    now = int(datetime.datetime.now().timestamp())
    return render_template('index.html', now=now)

@app.route('/process-csv', methods=['POST'])
def handle_csv_process():
    if 'csv_file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['csv_file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)

    try:
        # 嘗試讀取文件大小
        file_size = os.path.getsize(filepath)
        estimated_tokens = file_size / 6  # 粗略估算 token 數量
        
        # 對大文件使用批次處理
        large_file_threshold = 40000  # 約 40K tokens
        
        if estimated_tokens > large_file_threshold:
            print(f"檢測到大型 CSV 文件，估算約 {int(estimated_tokens)} tokens，將使用批次處理")
            from mcp_persona import process_large_csv
            output_csv_path, zip_path, all_personas_path, all_personas = asyncio.run(
                process_large_csv(filepath, app.config['OUTPUT_FOLDER'])
            )
        else:
            print(f"檢測到標準大小 CSV 文件，估算約 {int(estimated_tokens)} tokens，使用常規處理")
            output_csv_path, zip_path, all_personas_path, all_personas = asyncio.run(
                process_csv(filepath, app.config['OUTPUT_FOLDER'])
            )
        
        # 確保路徑只保留檔名部分，不包含完整路徑
        output_csv_basename = os.path.basename(output_csv_path)
        zip_basename = os.path.basename(zip_path)
        all_personas_basename = os.path.basename(all_personas_path)
        
        # 將相對路徑和其他資訊傳回前端
        response_data = {
            'success': True,
            'message': f'成功生成 {len(all_personas)} 個 personas',
            'csv_log_path': output_csv_basename,
            'zip_path': zip_basename,
            'personas_json_path': all_personas_basename,
            'persona_count': len(all_personas),
            'personas': all_personas  # 傳回完整的 personas 資料
        }
        
        # 記錄成功的回應用於除錯
        print(f"成功處理 CSV，回傳 {len(all_personas)} 個 personas")
        
        return jsonify(response_data)
    except Exception as e:
        # 詳細記錄錯誤
        print(f"CSV 處理錯誤: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

# 修改 process-csv2 路由以支持多文件上传
@app.route('/process-csv2', methods=['POST'])
def handle_csv2_process():
    if 'csv_file' not in request.files:
        return jsonify({'error': '沒有檔案部分'}), 400
    
    # 獲取 API Key 並設置環境變數
    api_key = request.form.get('api_key', '')
    if not api_key:
        return jsonify({'error': '未提供 Gemini API Key'}), 400
    
    os.environ["Gemini_api"] = api_key
    
    files = request.files.getlist('csv_file')
    if not files or files[0].filename == '':
        return jsonify({'error': '未選擇任何檔案'}), 400
    
    try:
        all_personas = []
        
        for i, file in enumerate(files):
            # 保存檔案
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
            file.save(filepath)
            
            print(f"處理第 {i+1}/{len(files)} 個檔案: {os.path.basename(filepath)}")
            
            # 估算檔案大小 - 使用一致的估算方法
            file_size = os.path.getsize(filepath)
            estimated_tokens = file_size / 6  # 統一使用這個方法估算
            large_file_threshold = 40000
            
            # 根據檔案大小選擇處理方法
            if estimated_tokens > large_file_threshold:
                print(f"檢測到大型 CSV2 檔案，估算約 {int(estimated_tokens)} tokens，將使用批次處理")
                from mcp_persona import process_large_csv2
                _, _, _, file_personas = asyncio.run(
                    process_large_csv2(filepath, app.config['OUTPUT_FOLDER'])
                )
            else:
                print(f"檢測到標準大小 CSV2 檔案，估算約 {int(estimated_tokens)} tokens，使用常規處理")
                _, _, _, file_personas = asyncio.run(
                    process_csv2(filepath, app.config['OUTPUT_FOLDER'])
                )
                
            # 合併結果
            if file_personas:
                all_personas.extend(file_personas)
        
        # 現在我們有了所有檔案的 personas，保存合併結果
        if not all_personas:
            return jsonify({'error': '未能生成任何 Persona'}), 500
            
        # 保存合併後的 personas
        out_dir = os.path.join(app.config['OUTPUT_FOLDER'], "personas", "csv2")
        os.makedirs(out_dir, exist_ok=True)
        
        # 合併所有 personas 成一個 json
        all_personas_path = os.path.join(app.config['OUTPUT_FOLDER'], "personas", "csv2_personas.json")
        with open(all_personas_path, 'w', encoding='utf-8') as f:
            json.dump(all_personas, f, ensure_ascii=False, indent=4)
        print(f"合併 personas 到 {all_personas_path}")
        
        # 壓縮成 zip
        zip_path = os.path.join(app.config['OUTPUT_FOLDER'], "csv2_personas.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(out_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, out_dir)
                    zipf.write(file_path, arcname)
        print(f"壓縮 personas 到 {zip_path}")
        
        # 返回結果
        return jsonify({
            'success': True,
            'message': f'成功生成 {len(all_personas)} 個 personas',
            'csv_log_path': "csv2_processing_log.txt",
            'zip_path': os.path.basename(zip_path),
            'personas_json_path': os.path.basename(all_personas_path),
            'persona_count': len(all_personas),
            'personas': all_personas
        })
    except Exception as e:
        print(f"CSV2 處理錯誤: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500
    
@app.route('/process-md', methods=['POST'])
def handle_md_process():
    if 'md_files[]' not in request.files:
        return jsonify({'error': 'No files part'}), 400
    files = request.files.getlist('md_files[]')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No selected files'}), 400
    
    md_paths = []
    for file in files:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(filepath)
        md_paths.append(filepath)

    try:
        output_md_path, zip_path, all_personas_path, all_personas = asyncio.run(process_md(md_paths, app.config['OUTPUT_FOLDER']))
        
        # 確保路徑只保留檔名部分，不包含完整路徑
        output_md_basename = os.path.basename(output_md_path)
        zip_basename = os.path.basename(zip_path)
        all_personas_basename = os.path.basename(all_personas_path)
        
        return jsonify({
            'success': True,
            'message': f'成功生成 {len(all_personas)} 個 personas',
            'csv_log_path': output_md_basename,  # 這裡還是叫 csv_log_path，但實際是 MD 的對話紀錄
            'zip_path': zip_basename,
            'personas_json_path': all_personas_basename,
            'persona_count': len(all_personas),
            'personas': all_personas
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/process-feedback', methods=['POST'])
def handle_feedback():
    try:
        data = request.get_json()
        selected_ids = data.get('selected_personas', [])
        marketing_copy = data.get('marketing_copy', '')
        request_id = data.get('request_id', datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
        
        print(f"[{request_id}] 收到評估請求: {len(selected_ids)} 個 Personas, 文案長度 {len(marketing_copy)} 字元")
        print(f"[{request_id}] 選擇的 Persona IDs: {selected_ids}")

        if not selected_ids:
            return jsonify({'error': '未選擇任何Persona'}), 400
        if not marketing_copy:
            return jsonify({'error': '未輸入行銷文案'}), 400

        # 搜尋所有 persona 檔案
        personas_dir = os.path.join(app.config['OUTPUT_FOLDER'], "personas")
        all_personas = []
        for folder in ["csv", "csv2", "md"]:
            folder_path = os.path.join(personas_dir, folder)
            if os.path.exists(folder_path):
                for filename in os.listdir(folder_path):
                    if filename.endswith(".json") and not filename.endswith("_personas.json"):
                        with open(os.path.join(folder_path, filename), 'r', encoding='utf-8') as f:
                            try:
                                persona = json.load(f)
                                all_personas.append(persona)
                            except Exception as e:
                                print(f"[{request_id}] 讀取 JSON 檔案出錯: {e}")

        # 記錄所有找到的 Persona ID
        found_ids = [str(p.get('persona_id')) for p in all_personas]
        print(f"[{request_id}] 系統中找到的所有 Persona IDs: {found_ids}")
        
        # 檢查哪些選擇的 ID 不存在
        missing_ids = [id for id in selected_ids if id not in found_ids]
        if missing_ids:
            print(f"[{request_id}] 警告: 找不到以下 {len(missing_ids)} 個選擇的 Persona IDs: {missing_ids}")
        
        # 過濾出被選到的 personas
        selected_personas = [p for p in all_personas if str(p.get('persona_id')) in selected_ids]

        if not selected_personas:
            return jsonify({'error': '找不到對應的Persona'}), 400

        print(f"[{request_id}] 準備呼叫評估函數，選擇了 {len(selected_personas)} 個 Personas")
        
        try:
            # 導入並調用 run_mcp_feedback 函數
            from mcp_feedback import run_mcp_feedback
            
            # 根據 run_mcp_feedback 的類型選擇適當的調用方式
            import inspect
            if inspect.iscoroutinefunction(run_mcp_feedback):
                # 如果是異步函數，使用 asyncio.run
                print("檢測到 run_mcp_feedback 是異步函數，使用 asyncio.run")
                result = asyncio.run(run_mcp_feedback(selected_personas, marketing_copy))
            else:
                # 如果是同步函數，直接調用
                print("檢測到 run_mcp_feedback 是同步函數，直接調用")
                result = run_mcp_feedback(selected_personas, marketing_copy)
            
            print(f"評估成功，結果類型: {type(result)}")
            
            # 解析結果
            if isinstance(result, tuple) and len(result) == 3:
                feedbacks, avg_score, chart_img = result
            else:
                feedbacks = result
                # 計算平均分數
                avg_score = 0
                if feedbacks and len(feedbacks) > 0:
                    avg_score = sum(item.get('score', 0) for item in feedbacks) / len(feedbacks)
                # 生成圖表
                from mcp_feedback import generate_chart
                chart_img = generate_chart(feedbacks, avg_score)
            
            return jsonify({
                'success': True,
                'feedback': feedbacks,
                'avg_score': avg_score,
                'chart': chart_img
            })
        
        except Exception as e:
            print(f"評估函數執行錯誤: {e}")
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    except Exception as e:
        print(f"評估處理整體錯誤: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
def generate_score_chart(feedback_data, avg_score):
    """生成評分圖表，返回 base64 編碼的圖片"""
    if not feedback_data:
        return ""
    
    # 準備繪圖資料
    import plotly.graph_objects as go
    import base64
    
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

@app.route('/download/<path:filename>', methods=['GET'])
def download_file(filename):
    try:
        return send_file(os.path.join(app.config['OUTPUT_FOLDER'], filename), as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/load-personas', methods=['GET'])
def load_saved_personas():
    try:
        # 嘗試取得 API Key（如果有）
        api_key = request.args.get('api_key', '')
        if api_key:
            os.environ["Gemini_api"] = api_key
        
        base_dir = os.path.join(app.config['OUTPUT_FOLDER'], "personas")
        personas = []
        all_personas = []  # 用於記錄所有載入的 personas
        filtered_personas = []  # 用於記錄過濾後的 personas
        
        # 列出所有可能的類型
        persona_types = ["csv", "csv2", "md"]
        
        for source in persona_types:
            json_path = os.path.join(base_dir, f"{source}_personas.json")
            print(f"嘗試載入: {json_path}")
            
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        print(f"原始從 {json_path} 載入 {len(data)} 個 personas")
                        all_personas.extend(data)
                        
                        # 過濾掉沒有 description 的
                        valid_data = [p for p in data if p.get('description')]
                        filtered_personas.extend(valid_data)
                        print(f"過濾後從 {json_path} 載入 {len(valid_data)} 個有效 personas")
                        personas.extend(valid_data)
                except Exception as e:
                    print(f"載入 {json_path} 時出錯: {e}")
            else:
                print(f"檔案 {json_path} 不存在")

        # 檢查是否有重複的 ID
        ids = [p.get('persona_id') for p in personas]
        unique_ids = set(ids)
        if len(ids) != len(unique_ids):
            print(f"警告：有 {len(ids) - len(unique_ids)} 個重複的 persona ID")
            duplicate_ids = [id for id in ids if ids.count(id) > 1]
            print(f"重複的 ID: {duplicate_ids}")
            
            # 移除重複的 personas，保留最後一個
            unique_personas = {}
            for p in personas:
                unique_personas[p.get('persona_id')] = p
            personas = list(unique_personas.values())

        personas.sort(key=lambda p: str(p.get('persona_id', '')))
        print(f"總共載入 {len(all_personas)} 個原始 personas，過濾後 {len(filtered_personas)} 個，去重後 {len(personas)} 個")
        
        return jsonify({'personas': personas})

    except Exception as e:
        print(f"載入Persona失敗: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
# 添加下载评估结果的路由
@app.route('/download-feedback', methods=['POST'])
def download_feedback():
    try:
        data = request.get_json()
        feedback = data.get('feedback', [])
        marketing_copy = data.get('marketing_copy', '')
        
        if not feedback:
            return jsonify({'error': '没有评估数据可下载'}), 400
            
        # 创建CSV内容
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入标题行
        writer.writerow(['行銷文案評估結果'])
        writer.writerow(['評估時間', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow([])
        writer.writerow(['文案內容:'])
        writer.writerow([marketing_copy])
        writer.writerow([])
        writer.writerow(['Persona ID', '分數', '願意購買理由', '不願意購買理由', '詳細反饋'])
        
        # 写入每个 persona 的评估结果
        for item in feedback:
            writer.writerow([
                item.get('persona_id', ''),
                item.get('score', ''),
                '; '.join(item.get('reasons_to_buy', [])),
                '; '.join(item.get('reasons_not_to_buy', [])),
                item.get('detail_feedback', '')
            ])
            
        # 保存CSV文件
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], f"feedback_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        with open(output_path, 'w', encoding='utf-8-sig') as f:
            f.write(output.getvalue())
            
        return send_file(output_path, as_attachment=True, download_name='persona_feedback.csv')
    except Exception as e:
        print(f"下载评估结果时出错: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        'status': 'ok', 
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'version': '1.0.0'
    })

# ============ 入口點 ============

if __name__ == '__main__':
    # 設置 Gunicorn 相關參數，方便在 Render 上部署
    port = int(os.environ.get('PORT', 5001))
    print(f"啟動 Persona 系統，監聽 {port} port...")
    # 確保應用綁定到 0.0.0.0 以接受所有連接
    app.run(host='0.0.0.0', port=port)