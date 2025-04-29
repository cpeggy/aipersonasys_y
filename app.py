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

@app.route('/process-csv2', methods=['POST'])
def handle_csv2_process():
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
            print(f"檢測到大型 CSV2 文件，估算約 {int(estimated_tokens)} tokens，將使用批次處理")
            from mcp_persona import process_large_csv2
            output_csv_path, zip_path, all_personas_path, all_personas = asyncio.run(
                process_large_csv2(filepath, app.config['OUTPUT_FOLDER'])
            )
        else:
            print(f"檢測到標準大小 CSV2 文件，估算約 {int(estimated_tokens)} tokens，使用常規處理")
            output_csv_path, zip_path, all_personas_path, all_personas = asyncio.run(
                process_csv2(filepath, app.config['OUTPUT_FOLDER'])
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
        print(f"成功處理 CSV2，回傳 {len(all_personas)} 個 personas")
        
        return jsonify(response_data)
    except Exception as e:
        # 詳細記錄錯誤
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
        print(f"收到評估請求: {len(selected_ids)} 個 Personas, 文案長度 {len(marketing_copy)} 字元")

        if not selected_ids:
            return jsonify({'error': '未選擇任何Persona'}), 400
        if not marketing_copy:
            return jsonify({'error': '未輸入行銷文案'}), 400

        # 搜尋所有 persona 檔案
        personas_dir = os.path.join(app.config['OUTPUT_FOLDER'], "personas")
        all_personas = []
        for folder in ["csv", "md"]:
            folder_path = os.path.join(personas_dir, folder)
            if os.path.exists(folder_path):
                for filename in os.listdir(folder_path):
                    if filename.endswith(".json") and not filename.endswith("_personas.json"):
                        with open(os.path.join(folder_path, filename), 'r', encoding='utf-8') as f:
                            try:
                                persona = json.load(f)
                                all_personas.append(persona)
                            except Exception as e:
                                print(f"讀取 JSON 檔案出錯: {e}")

        # 過濾出被選到的 personas
        selected_personas = [p for p in all_personas if str(p.get('persona_id')) in selected_ids]

        if not selected_personas:
            return jsonify({'error': '找不到對應的Persona'}), 400

        print(f"準備呼叫評估函數，選擇了 {len(selected_personas)} 個 Personas")
        
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
        base_dir = os.path.join(app.config['OUTPUT_FOLDER'], "personas")
        personas = []

        for source in ["csv", "csv2", "md"]:
            json_path = os.path.join(base_dir, f"{source}_personas.json")
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 🔥 過濾掉沒有 description 的
                    data = [p for p in data if p.get('description')]
                    personas.extend(data)

        personas.sort(key=lambda p: str(p.get('persona_id', '')))
        print(personas)
        return jsonify({'personas': personas})

    except Exception as e:
        print(f"載入Persona失敗: {e}")
        traceback.print_exc()
        return jsonify({'personas': []})

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        'status': 'ok', 
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'version': '1.0.0'
    })

# ============ 入口點 ============

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"啟動 Persona 系統，監聽 {port} port...")
    app.run(debug=True, host='0.0.0.0', port=port)