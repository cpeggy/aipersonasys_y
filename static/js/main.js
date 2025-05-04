/**
 * Persona 系統前端 JavaScript
 * 
 * 這個文件包含 Persona 系統的所有前端功能，包括：
 * - API Key 管理
 * - 頁面導航
 * - Persona 生成與管理
 * - 行銷文案評估
 * - 資料視覺化
 */

// ====== 全域變數 ======
let savedPersonas = [];
const APP_VERSION = Date.now();
let isProcessing = false; // 防止重複處理的標記

// ====== 初始化 ======
$(document).ready(function() {
    console.log(`Persona 系統初始化 v${APP_VERSION}`);
    
    // 1. 初始化 API Key
    initializeAPIKey();
    
    // 2. 設置事件監聽器
    setupEventListeners();
    
    // 3. 載入 Persona 資料
    if ($('#feedback-tab').is(':visible')) {
        loadPersonas();
    } else {
        loadSavedPersonas();
    }
});

// ====== API Key 管理 ======
function initializeAPIKey() {
    // 從 localStorage 讀取 API Key
    const savedApiKey = localStorage.getItem('geminiApiKey'); // 統一使用 geminiApiKey
    if (savedApiKey) {
        $('#gemini-key').val(savedApiKey);
        console.log('已從 localStorage 載入 API Key');
    }
}

// 設置 API Key 相關事件
function setupAPIKeyEvents() {
    // 儲存 API Key
    $('#save-api-key').on('click', function() {
        const apiKey = $('#gemini-key').val().trim();
        if (apiKey) {
            localStorage.setItem('geminiApiKey', apiKey); // 使用相同的 key
            showToast('API Key 已儲存成功！', 'success');
            console.log('API Key 已儲存到 localStorage');
        } else {
            showToast('請輸入有效的 API Key', 'warning');
        }
    });
}

// ====== 事件監聽器設置 ======
function setupEventListeners() {
    // 清除所有可能的事件綁定，確保不會重複
    clearAllEventListeners();
    
    // API Key 管理
    setupAPIKeyEvents();
    
    // 導航事件
    setupNavigationEvents();
    
    // 按鈕事件
    setupButtonEvents();
    
    // 全選 Persona 事件
    setupSelectAllEvent();
}

// 清除所有可能的事件綁定
function clearAllEventListeners() {
    // API Key 相關
    $('#save-api-key').off('click');
    $('#toggle-api-sidebar').off('click');
    
    // 導航相關
    $('#nav-generate').off('click');
    $('#nav-feedback').off('click');
    
    // 按鈕相關
    $('#csv-submit').off('click');
    $('#csv2-submit').off('click');
    $('#md-submit').off('click');
    $('#feedback-submit').off('click');
    $('#refresh-personas-btn').off('click');
    $('#download-feedback-btn').off('click');
    $('#feedback-form').off('submit');
    
    // 全選相關
    $('#select-all-personas').off('change');
}

// 設置 API Key 相關事件
function setupAPIKeyEvents() {
    // 儲存 API Key
    $('#save-api-key').on('click', function() {
        const apiKey = $('#gemini-key').val().trim();
        if (apiKey) {
            localStorage.setItem('geminiApiKey', apiKey);
            showToast('API Key 已儲存', 'success');
        } else {
            showToast('請輸入有效的 API Key', 'warning');
        }
    });
    
    // 在小螢幕上切換 API 側邊欄
    $('#toggle-api-sidebar').on('click', function() {
        $('.api-key-sidebar').toggleClass('show');
    });
    
    // 點擊頁面其他區域關閉側邊欄（僅在小螢幕）
    $(document).on('click', function(event) {
        if (!$(event.target).closest('.api-key-sidebar').length && 
            !$(event.target).closest('#toggle-api-sidebar').length &&
            $('.api-key-sidebar').hasClass('show') &&
            $(window).width() < 768) {
            $('.api-key-sidebar').removeClass('show');
        }
    });
}

// 設置導航事件
function setupNavigationEvents() {
    $('#nav-generate').on('click', function() {
        $('.tab-pane').hide();
        $('#generate-tab').show();
        $('.nav-link').removeClass('active');
        $(this).addClass('active');
    });
    
    $('#nav-feedback').on('click', function() {
        $('.tab-pane').hide();
        $('#feedback-tab').show();
        $('.nav-link').removeClass('active');
        $(this).addClass('active');
        
        // 切換到評估頁面時載入 Persona 資料
        if (!isProcessing) {
            loadPersonas();
        }
    });
}

// 設置按鈕事件
function setupButtonEvents() {
    // CSV 上傳處理
    $('#csv-submit').on('click', function() {
        if (isProcessing) return;
        isProcessing = true;
        
        processCSVForm().finally(() => {
            isProcessing = false;
        });
    });
    
    // CSV2 上傳處理
    $('#csv2-submit').on('click', function() {
        if (isProcessing) return;
        isProcessing = true;
        
        processCSV2Form().finally(() => {
            isProcessing = false;
        });
    });
    
    // MD 上傳處理
    $('#md-submit').on('click', function() {
        if (isProcessing) return;
        isProcessing = true;
        
        processMDForm().finally(() => {
            isProcessing = false;
        });
    });
    
    // 評估處理
    $('#feedback-submit').on('click', function() {
        if (isProcessing || $(this).prop('disabled')) return;
        isProcessing = true;
        $(this).prop('disabled', true);
        
        processFeedbackForm().finally(() => {
            isProcessing = false;
            $(this).prop('disabled', false);
        });
    });
    
    // 防止表單自動提交
    $('#feedback-form').on('submit', function(e) {
        e.preventDefault();
    });
    
    // 刷新 Persona 按鈕
    $('#refresh-personas-btn').on('click', function() {
        if (isProcessing) return;
        isProcessing = true;
        
        loadPersonas().finally(() => {
            isProcessing = false;
        });
    });
    
    // 下載評估結果按鈕
    $('#download-feedback-btn').on('click', function() {
        if (isProcessing) return;
        isProcessing = true;
        
        downloadAllFeedback().finally(() => {
            isProcessing = false;
        });
    });
}

// 設置全選事件
function setupSelectAllEvent() {
    $('#select-all-personas').on('change', function() {
        if ($(this).is(':checked')) {
            $('.persona-card').addClass('selected');
        } else {
            $('.persona-card').removeClass('selected');
        }
    });
}

// ====== 通用提示訊息顯示函數 ======
function showToast(message, type = 'info') {
    // 若頁面上沒有 toast 容器，則創建一個
    if ($('#toast-container').length === 0) {
        $('body').append('<div id="toast-container" class="position-fixed bottom-0 end-0 p-3" style="z-index: 1100;"></div>');
    }
    
    // 生成唯一 ID
    const toastId = 'toast-' + Date.now();
    
    // 設置樣式
    let headerClass = '';
    let bodyClass = '';
    let textClass = '';
    let btnCloseClass = 'btn-close';
    
    if (type === 'success') {
        headerClass = 'bg-success text-white';
        bodyClass = '';
        textClass = '';
        btnCloseClass = 'btn-close-white';
    } else if (type === 'warning') {
        headerClass = 'bg-warning text-dark';
        bodyClass = 'bg-white';
        textClass = 'text-dark';
    } else if (type === 'danger') {
        headerClass = 'bg-danger text-white';
        bodyClass = '';
        textClass = '';
        btnCloseClass = 'btn-close-white';
    } else if (type === 'info') {
        headerClass = 'bg-info text-white';
        bodyClass = '';
        textClass = '';
        btnCloseClass = 'btn-close-white';
    }
    
    // 創建 toast HTML
    const toastHtml = `
    <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="toast-header ${headerClass}">
        <strong class="me-auto">系統訊息</strong>
        <button type="button" class="${btnCloseClass}" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
      <div class="toast-body ${bodyClass} ${textClass}">
        ${message}
      </div>
    </div>
    `;
    
    // 添加到容器
    $('#toast-container').append(toastHtml);
    
    // 初始化並顯示 toast
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { autohide: true, delay: 3000 });
    toast.show();
    
    // 自動移除
    setTimeout(function() {
        $(`#${toastId}`).remove();
    }, 3500);
}

// ====== 上傳 CSV 處理 ======
function processCSVForm() {
    return new Promise((resolve, reject) => {
        const apiKey = $('#gemini-key').val().trim();
        if (!apiKey) {
            showToast('請先設定 Gemini API Key', 'warning');
            resolve();
            return;
        }
        
        const fileInput = $('#csv-file')[0];
        if (fileInput.files.length === 0) {
            showToast('請選擇CSV檔案', 'warning');
            resolve();
            return;
        }
        
        // 顯示進度條
        $('#csv-progress').removeClass('d-none');
        $('#csv-result').addClass('d-none');
        $('#csv-submit').prop('disabled', true);
        
        // 創建FormData對象
        const formData = new FormData();
        formData.append('csv_file', fileInput.files[0]);
        formData.append('api_key', apiKey);  // 添加API Key
        
        // 發送AJAX請求
        $.ajax({
            url: '/process-csv',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                // 隱藏進度條，恢復按鈕
                $('#csv-progress').addClass('d-none');
                $('#csv-submit').prop('disabled', false);
                
                console.log("處理 CSV 成功，伺服器回應:", response);
                
                if (response.success) {
                    // 更新 persona 數量
                    $('#csv-persona-count').text(response.persona_count);
                    
                    // 更新下載連結
                    $('#csv-download-zip').attr('href', `/download/${response.zip_path}`);
                    $('#csv-download-log').attr('href', `/download/${response.csv_log_path}`);
                    
                    // 顯示結果區域
                    $('#csv-result').removeClass('d-none');
                    
                    // 顯示批次資訊（如果有的話）
                    if (response.personas.length > 0 && response.personas[0].batch_info) {
                        const batches = [...new Set(response.personas.map(p => p.batch_info))];
                        const batchInfoHtml = `
                            <div class="alert alert-info mt-2">
                              <small>已使用 ${batches.length} 個批次處理 (${batches.join(', ')})</small>
                            </div>`;
                        $('#csv-result').append(batchInfoHtml);
                    }
                    
                    // 更新前端的 persona 列表
                    savedPersonas = response.personas;
                    updatePersonaSelections();
                    loadPersonas(); // 重新載入 persona 列表
                } else {
                    showToast('處理完成但後端回傳 success=false', 'warning');
                    console.error("非預期回應：", response);
                }
                
                resolve(response);
            },
            error: function(error) {
                $('#csv-progress').addClass('d-none');
                $('#csv-submit').prop('disabled', false);
                showToast('處理CSV檔案時出錯: ' + (error.responseJSON ? error.responseJSON.error : '未知錯誤'), 'danger');
                console.error('Error:', error);
                reject(error);
            }
        });
    });
}

// ====== 上傳 CSV2 處理 - 支援多檔案 ======
function processCSV2Form() {
    return new Promise((resolve, reject) => {
        const apiKey = $('#gemini-key').val().trim();
        if (!apiKey) {
            showToast('請先設定 Gemini API Key', 'warning');
            resolve();
            return;
        }
        
        const files = $('#csv2-file')[0].files;
        if(files.length === 0) {
            showToast('請選擇至少一個CSV檔案', 'warning');
            resolve();
            return;
        }
        
        // 顯示進度條
        $('#csv2-progress').removeClass('d-none');
        $('#csv2-result').addClass('d-none');
        $('#csv2-submit').prop('disabled', true);
        
        // 創建FormData對象
        const formData = new FormData();
        for(let i = 0; i < files.length; i++) {
            formData.append('csv_file', files[i]);
        }
        formData.append('api_key', apiKey);  // 添加API Key
        
        // 發送AJAX請求
        $.ajax({
            url: '/process-csv2',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                $('#csv2-progress').addClass('d-none');
                $('#csv2-submit').prop('disabled', false);
                
                console.log("處理 CSV2 成功，伺服器回應:", response);
                
                if (response.success) {
                    // 更新 persona 數量
                    $('#csv2-persona-count').text(response.persona_count);
                    
                    // 更新下載連結
                    $('#csv2-download-zip').attr('href', `/download/${response.zip_path}`);
                    $('#csv2-download-log').attr('href', `/download/${response.csv_log_path}`);
                    
                    // 顯示結果區域
                    $('#csv2-result').removeClass('d-none');
                    
                    // 更新前端的 persona 列表
                    if (response.personas && response.personas.length > 0) {
                        savedPersonas = response.personas;
                        updatePersonaSelections();
                        loadPersonas(); // 重新載入 persona 列表
                    } else {
                        console.warn("回應中沒有 personas 資料或為空陣列");
                    }
                } else {
                    showToast('處理完成但回應格式異常', 'warning');
                    console.error("回應格式不符合預期:", response);
                }
                
                resolve(response);
            },
            error: function(error) {
                $('#csv2-progress').addClass('d-none');
                $('#csv2-submit').prop('disabled', false);
                showToast('處理CSV檔案時出錯: ' + (error.responseJSON ? error.responseJSON.error : '未知錯誤'), 'danger');
                console.error('Error:', error);
                reject(error);
            }
        });
    });
}

// ====== 上傳 MD 處理 ======
function processMDForm() {
    return new Promise((resolve, reject) => {
        const apiKey = $('#gemini-key').val().trim();
        if (!apiKey) {
            showToast('請先設定 Gemini API Key', 'warning');
            resolve();
            return;
        }
        
        const files = $('#md-files')[0].files;
        if(files.length === 0) {
            showToast('請選擇至少一個MD檔案', 'warning');
            resolve();
            return;
        }
        
        // 顯示進度條
        $('#md-progress').removeClass('d-none');
        $('#md-result').addClass('d-none');
        $('#md-submit').prop('disabled', true);
        
        // 創建FormData對象
        const formData = new FormData();
        for(let i = 0; i < files.length; i++) {
            formData.append('md_files[]', files[i]);
        }
        formData.append('api_key', apiKey);  // 添加API Key
        
        // 發送AJAX請求
        $.ajax({
            url: '/process-md',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                $('#md-progress').addClass('d-none');
                $('#md-submit').prop('disabled', false);
                
                console.log("處理 MD 成功，伺服器回應:", response);
                
                if (response.success) {
                    // 更新 persona 數量
                    $('#md-persona-count').text(response.persona_count);
                    
                    // 更新下載連結
                    $('#md-download-zip').attr('href', `/download/${response.zip_path}`);
                    $('#md-download-log').attr('href', `/download/${response.csv_log_path}`);
                    
                    // 顯示結果區域
                    $('#md-result').removeClass('d-none');
                    
                    // 更新前端的 persona 列表
                    if (response.personas && response.personas.length > 0) {
                        savedPersonas = response.personas;
                        updatePersonaSelections();
                        loadPersonas(); // 重新載入 persona 列表
                    } else {
                        console.warn("回應中沒有 personas 資料或為空陣列");
                    }
                } else {
                    showToast('處理完成但回應格式異常', 'warning');
                    console.error("回應格式不符合預期:", response);
                }
                
                resolve(response);
            },
            error: function(error) {
                $('#md-progress').addClass('d-none');
                $('#md-submit').prop('disabled', false);
                showToast('處理MD檔案時出錯: ' + (error.responseJSON ? error.responseJSON.error : '未知錯誤'), 'danger');
                console.error('Error:', error);
                reject(error);
            }
        });
    });
}

// ====== Feedback 評估表單處理 ======
function processFeedbackForm() {
    return new Promise((resolve, reject) => {
        const apiKey = $('#gemini-key').val().trim();
        if (!apiKey) {
            showToast('請先設定 Gemini API Key', 'warning');
            resolve();
            return;
        }
        
        // 獲取選中的persona IDs
        const selectedIds = [];
        $('.persona-card.selected').each(function() {
            const id = $(this).data('id');
            if (id) {
                selectedIds.push(id);
                console.log(`已選擇 Persona: ${id}`);
            }
        });
        
        console.log(`總共選擇了 ${selectedIds.length} 個 Personas: ${selectedIds.join(', ')}`);
        
        const marketingCopy = $('#marketing-copy').val().trim();
        
        if(selectedIds.length === 0) {
            showToast('請至少選擇一個Persona', 'warning');
            resolve();
            return;
        }
        
        if(marketingCopy === '') {
            showToast('請輸入行銷文案', 'warning');
            resolve();
            return;
        }
        
        // 顯示進度條
        $('#feedback-progress').removeClass('d-none');
        $('#feedback-result').addClass('d-none');
        $('#feedback-submit').prop('disabled', true);
        
        // 創建分段進度條 - 每個批次（2個Persona）一個分段
        const batchSize = 2;
        const totalBatches = Math.ceil(selectedIds.length / batchSize);
        createSegmentedProgressBar('feedback-progress', totalBatches);
        
        // 初始化進度 - 從0開始
        updateSegmentedProgress('feedback-progress', 0, totalBatches, 
            `準備評估 ${selectedIds.length} 個 Persona...`, '');
        
        // 生成唯一請求ID
        const requestId = Date.now();
        console.log(`[${requestId}] 開始處理評估請求`);
        
        // 發送請求並處理串流回應
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/process-feedback', true);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.setRequestHeader('Accept', 'text/event-stream');
        
        // 用於儲存累積的回應和上次處理的位置
        let lastProcessedPosition = 0;
        
        xhr.onprogress = function(e) {
            const currentResponse = e.currentTarget.responseText;
            const newData = currentResponse.substring(lastProcessedPosition);
            lastProcessedPosition = currentResponse.length;

            console.log('收到新數據:', newData);  // 調試用

            const lines = newData.split('\n');
            
            lines.forEach(line => {
            if (line.startsWith('data: ')) {
                try {
                    const dataStr = line.substring(6);
                    if (dataStr.trim()) {
                        const data = JSON.parse(dataStr);
                        console.log('解析的數據:', data);  // 調試用
                        
                        if (data.type === 'progress') {
                            // 更新進度條
                            console.log('更新進度條:', data.batch_current, '/', data.batch_total);
                            updateSegmentedProgress(
                                'feedback-progress', 
                                data.batch_current, 
                                data.batch_total, 
                                data.message, 
                                data.batch_message
                            );
                            } else if (data.type === 'complete') {
                            // 處理完成
                            console.log('處理完成');
                            $('#feedback-progress').addClass('d-none');
                            $('#feedback-submit').prop('disabled', false);
                            
                            if (data.success) {
                                // 顯示結果區域
                                $('#feedback-result').removeClass('d-none');
                                
                                // 設置圖表
                                if (data.chart) {
                                    $('#score-chart').attr('src', 'data:image/png;base64,' + data.chart);
                                } else {
                                    $('#score-chart').html('<div class="alert alert-warning">無法生成圖表</div>');
                                }
                                
                                // 處理其他結果數據
                                processBuyReasons(data.feedback);
                                generateFeedbackCards(data.feedback);
                                
                                window.feedbackData = data.feedback;
                                window.marketingCopy = marketingCopy;
                                
                                setupFeedbackModal();
                                showToast('評估完成！', 'success');
                            } else {
                                showToast('評估失敗: ' + (data.error || '未知錯誤'), 'danger');
                            }
                            
                            resolve(data);
                        } else if (data.type === 'error') {
                            console.error('處理錯誤:', data.error);
                            $('#feedback-progress').addClass('d-none');
                            $('#feedback-submit').prop('disabled', false);
                            showToast('處理反饋時出錯: ' + data.error, 'danger');
                            reject(new Error(data.error));
                        }
                        }
                    } catch (error) {
                        console.error('解析串流數據錯誤:', error, 'Line:', line);
                    }
                }
            });
        };
        
        xhr.onload = function() {
            if (xhr.status !== 200) {
                $('#feedback-progress').addClass('d-none');
                $('#feedback-submit').prop('disabled', false);
                let errorMessage = '處理反饋時出錯';
                try {
                    const errorData = JSON.parse(xhr.responseText);
                    errorMessage += ': ' + errorData.error;
                } catch (e) {
                    errorMessage += ': ' + xhr.statusText;
                }
                showToast(errorMessage, 'danger');
                reject(new Error(errorMessage));
            }
        };
        
        xhr.onerror = function() {
            $('#feedback-progress').addClass('d-none');
            $('#feedback-submit').prop('disabled', false);
            showToast('網絡錯誤', 'danger');
            reject(new Error('網絡錯誤'));
        };
        
        xhr.ontimeout = function() {
            $('#feedback-progress').addClass('d-none');
            $('#feedback-submit').prop('disabled', false);
            showToast('請求超時', 'danger');
            reject(new Error('請求超時'));
        };
        
        // 設置超時時間
        xhr.timeout = 600000; // 10分鐘
        
        // 發送請求數據
        xhr.send(JSON.stringify({
            selected_personas: selectedIds,
            marketing_copy: marketingCopy,
            api_key: apiKey,
            request_id: requestId
        }));
    });
}

// 設置反饋詳情對話框
function setupFeedbackModal() {
    if (!$('#feedbackModal').length) {
        $('body').append(`
            <div class="modal fade" id="feedbackModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Persona <span id="modal-persona-id"></span> 評估詳情</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <pre id="modal-feedback-content" class="p-3 bg-light rounded"></pre>
                        </div>
                    </div>
                </div>
            </div>
        `);
        
        // 添加對話框事件處理
        $('#feedbackModal').on('show.bs.modal', function (event) {
            const button = $(event.relatedTarget);
            const feedback = decodeURIComponent(button.data('feedback'));
            const personaId = button.data('persona');
            
            $('#modal-persona-id').text(personaId);
            $('#modal-feedback-content').text(feedback);
        });
    }
}

// ====== 處理購買理由和不購買理由 ======
function processBuyReasons(feedback) {
    // 收集所有購買理由
    let allBuyReasons = [];
    let allNotBuyReasons = [];
    
    feedback.forEach(function(item) {
        if (item.reasons_to_buy && Array.isArray(item.reasons_to_buy)) {
            allBuyReasons = allBuyReasons.concat(item.reasons_to_buy);
        }
        if (item.reasons_not_to_buy && Array.isArray(item.reasons_not_to_buy)) {
            allNotBuyReasons = allNotBuyReasons.concat(item.reasons_not_to_buy);
        }
    });
    
    // 去重並顯示
    const uniqueBuyReasons = [...new Set(allBuyReasons)];
    const uniqueNotBuyReasons = [...new Set(allNotBuyReasons)];
    
    // 生成HTML
    let buyReasonsHtml = '<ul class="reasons-list">';
    uniqueBuyReasons.forEach(function(reason) {
        buyReasonsHtml += `<li>${reason}</li>`;
    });
    buyReasonsHtml += '</ul>';
    
    let notBuyReasonsHtml = '<ul class="reasons-list">';
    uniqueNotBuyReasons.forEach(function(reason) {
        notBuyReasonsHtml += `<li>${reason}</li>`;
    });
    notBuyReasonsHtml += '</ul>';
    
    // 顯示到頁面
    $('#buy-reasons').html(buyReasonsHtml);
    $('#not-buy-reasons').html(notBuyReasonsHtml);
}

// ====== 生成個別Persona反饋卡片 ======
function generateFeedbackCards(feedback) {
    let html = '';
    
    feedback.forEach(function(item) {
        // 根據評分決定顏色
        let colorClass = '';
        if (item.score >= 8) {
            colorClass = 'border-success';
        } else if (item.score >= 6) {
            colorClass = 'border-primary';
        } else if (item.score >= 4) {
            colorClass = 'border-warning';
        } else {
            colorClass = 'border-danger';
        }
        
        html += `
        <div class="col-md-6 mb-4">
            <div class="card persona-feedback-card ${colorClass}">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">Persona ${item.persona_id}</h6>
                    <span class="badge bg-${item.score >= 8 ? 'success' : item.score >= 6 ? 'primary' : item.score >= 4 ? 'warning' : 'danger'} score-badge">
                        評分: ${item.score}/10
                    </span>
                </div>
                <div class="card-body feedback-content">
                    <h6>購買理由:</h6>
                    <ul class="reasons-list">
                        ${item.reasons_to_buy ? item.reasons_to_buy.map(reason => `<li>${reason}</li>`).join('') : '<li>無</li>'}
                    </ul>
                    <h6>不購買理由:</h6>
                    <ul class="reasons-list">
                        ${item.reasons_not_to_buy ? item.reasons_not_to_buy.map(reason => `<li>${reason}</li>`).join('') : '<li>無</li>'}
                    </ul>
                    <button class="btn btn-sm btn-outline-secondary mt-2" 
                            data-bs-toggle="modal" 
                            data-bs-target="#feedbackModal" 
                            data-feedback="${encodeURIComponent(item.detail_feedback || '')}"
                            data-persona="${item.persona_id}">
                        查看完整評估
                    </button>
                </div>
            </div>
        </div>`;
    });
    
    $('#persona-feedback-cards').html(html);
}

// ====== 下載所有反饋結果 ======
function downloadAllFeedback() {
    return new Promise((resolve, reject) => {
        const apiKey = $('#gemini-key').val().trim();
        if (!apiKey) {
            showToast('請先設定 Gemini API Key', 'warning');
            resolve();
            return;
        }
        
        if(!window.feedbackData || window.feedbackData.length === 0) {
            showToast('沒有可下載的反饋數據', 'warning');
            resolve();
            return;
        }
        
        // 使用服務器端處理下載
        $.ajax({
            url: '/download-feedback',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                feedback: window.feedbackData,
                marketing_copy: window.marketingCopy,
                api_key: apiKey
            }),
            xhrFields: {
                responseType: 'blob' // 設置為blob以接收二進制數據
            },
            success: function(response) {
                // 創建一個下載連結
                const url = window.URL.createObjectURL(new Blob([response]));
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = 'persona_feedback_' + new Date().toISOString().slice(0,10) + '.csv';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                showToast('評估結果已下載', 'success');
                resolve(response);
            },
            error: function(error) {
                showToast('下載反饋結果時出錯', 'danger');
                console.error('Error:', error);
                reject(error);
            }
        });
    });
}

// ====== 載入本地已儲存 Persona ======
function loadSavedPersonas() {
    return new Promise((resolve, reject) => {
        console.log("載入儲存 Persona");
        $.ajax({
            url: '/load-personas',
            type: 'GET',
            success: function(response) {
                console.log("載入到的 personas 數量:", response.personas ? response.personas.length : 0);
                
                if (response.personas) {
                    savedPersonas = response.personas;
                    updatePersonaSelections();
                }
                
                resolve(response);
            },
            error: function(error) {
                console.error("載入 Persona 失敗:", error);
                reject(error);
            }
        });
    });
}

// ====== 更新 Persona 選擇清單 - 舊版UI ======
function updatePersonaSelections() {
    const container = $('#persona-selection');
    if (!container.length) return;
    
    container.empty();
    
    if (savedPersonas.length === 0) {
        container.html('<div class="alert alert-info"><i class="fas fa-info-circle"></i> 未找到任何Persona，請先生成</div>');
        return;
    }

    savedPersonas.sort((a, b) => a.persona_id.localeCompare(b.persona_id));

    savedPersonas.forEach(persona => {
        if (!persona.description) return;
        const html = `
            <div class="persona-card" data-persona-id="${persona.persona_id}">
                <div class="card-body">
                    <div class="form-check">
                        <input class="form-check-input persona-checkbox" type="checkbox" value="${persona.persona_id}" id="persona-${persona.persona_id}">
                        <label class="form-check-label w-100" for="persona-${persona.persona_id}">
                            <div class="persona-title">Persona ${persona.persona_id}</div>
                            <div class="persona-description">${persona.description.substring(0, 100)}...</div>
                        </label>
                    </div>
                </div>
            </div>
        `;
        container.append(html);
    });
}

// ====== 加載所有保存的Persona - 新版UI ======
function loadPersonas() {
    return new Promise((resolve, reject) => {
        // 顯示加載指示器
        $('#persona-selection').html('<div class="text-center py-3"><div class="spinner-border text-primary"></div><p class="mt-2">正在加載 Persona...</p></div>');
        
        // 取消全選複選框的選中狀態
        $('#select-all-personas').prop('checked', false);
        
        // 取得 API Key
        const apiKey = $('#gemini-key').val().trim();
        
        // 發送AJAX請求獲取Persona數據
        $.ajax({
            url: '/load-personas',
            type: 'GET',
            data: apiKey ? { api_key: apiKey } : {}, // 如果有 API Key 就傳送
            success: function(response) {
                console.log("載入到的 personas 數量:", response.personas ? response.personas.length : 0);
                console.log("persona 類型:", response.personas ? [...new Set(response.personas.map(p => p.persona_id.split('_')[0]))] : []);
                
                if(response.personas && response.personas.length > 0) {
                    displayPersonas(response.personas);
                } else {
                    $('#persona-selection').html('<div class="alert alert-info"><i class="fas fa-info-circle"></i> 未找到任何Persona，請先生成</div>');
                }
                
                resolve(response);
            },
            error: function(error) {
                console.error('加載Persona失敗:', error);
                $('#persona-selection').html('<div class="alert alert-danger"><i class="fas fa-exclamation-circle"></i> 加載Persona失敗</div>');
                reject(error);
            }
        });
    });
}

// ====== 顯示Persona卡片 - 新版UI ======
function displayPersonas(personas) {
    let html = '';
    
    console.log("準備顯示的 Personas:", personas.map(p => p.persona_id));
    
    personas.forEach(function(persona) {
        const personaId = persona.persona_id || "無ID";
        
        html += `
        <div class="persona-card p-3 mb-3" data-id="${personaId}">
            <div class="persona-title">${personaId}: ${persona.description ? persona.description.substring(0, 50) + '...' : '無描述'}</div>
            <div class="persona-description">
                <strong>學習動機：</strong> ${persona.motivation ? persona.motivation.substring(0, 50) + '...' : '無'}
            </div>
            <div class="persona-description">
                <strong>面臨挑戰：</strong> ${persona.challenges ? persona.challenges.substring(0, 50) + '...' : '無'}
            </div>
        </div>`;
    });
    
    $('#persona-selection').html(html);
    
    // 添加點擊事件來選擇/取消選擇persona卡片
    $('.persona-card').click(function() {
        $(this).toggleClass('selected');
        // 檢查是否所有卡片都被選中
        updateSelectAllCheckbox();
    });
    
    console.log(`顯示了 ${personas.length} 個 Personas`);
}

// ====== 更新全選複選框狀態 ======
function updateSelectAllCheckbox() {
    const totalCards = $('.persona-card').length;
    const selectedCards = $('.persona-card.selected').length;
    
    if(totalCards > 0 && totalCards === selectedCards) {
        $('#select-all-personas').prop('checked', true);
    } else {
        $('#select-all-personas').prop('checked', false);
    }
}

// ====== 畫出購買意願分數長條圖 ======
function drawScoreChart(feedback, avgScore) {
    if (!feedback || feedback.length === 0) {
        $('#score-chart').html('<div class="alert alert-info">目前沒有可顯示的評估資料。</div>');
        return;
    }

    const labels = feedback.map(item => `Persona-${item.persona_id}`);
    const scores = feedback.map(item => item.score);

    const trace = {
        x: scores,
        y: labels,
        type: 'bar',
        orientation: 'h',
        text: scores.map(String),
        textposition: 'outside',
        hoverinfo: 'x+y',
        marker: {
            color: scores.map(s =>
                s >= 8 ? 'green' :
                s >= 6 ? 'blue' :
                s >= 4 ? 'orange' : 'red'
            )
        }
    };

    const layout = {
        title: '各 Persona 購買意願分數',
        shapes: [{
            type: 'line',
            x0: avgScore, x1: avgScore,
            y0: -0.5, y1: labels.length - 0.5,
            line: { color: 'red', width: 2, dash: 'dash' }
        }],
        annotations: [{
            x: avgScore,
            y: labels.length - 0.5,
            text: `平均購買意願 ${avgScore.toFixed(1)}`,
            showarrow: true,
            arrowhead: 2,
            ax: 40,
            ay: -40
        }],
        margin: { l: 100 },
        xaxis: { title: '得分', range: [0, 10] },
        yaxis: { title: 'Persona' }
    };

    Plotly.newPlot('score-chart', [trace], layout);
}

// ====== 通用進度更新函數 ======
function updateProgress(progressBarId, current, total, message = '') {
    const progressBar = $(`#${progressBarId} .progress-bar`);
    const percentage = Math.round((current / total) * 100);
    
    progressBar.css('width', percentage + '%');
    progressBar.attr('aria-valuenow', percentage);
    
    // 如果有進度文字區域，更新文字
    const progressText = $(`#${progressBarId}-text`);
    if (progressText.length && message) {
        progressText.text(message);
    }
}

// ====== 創建分段進度條 ======
function createSegmentedProgressBar(progressBarId, totalSegments) {
    const container = $(`#${progressBarId}`);
    container.empty();
    
    // 創建進度條外容器
    const wrapper = $('<div>').addClass('segmented-progress-wrapper');
    
    // 創建分段
    for (let i = 0; i < totalSegments; i++) {
        const segment = $('<div>')
            .addClass('progress-segment')
            .attr('data-segment', i);
        wrapper.append(segment);
    }
    
    container.append(wrapper);
    
    // 添加進度文字區域
    const progressText = $('<div>')
        .addClass('progress-text')
        .attr('id', `${progressBarId}-text`);
    container.append(progressText);
    
    // 添加批次信息文字
    const batchInfo = $('<div>')
        .addClass('batch-info')
        .attr('id', `${progressBarId}-batch`);
    container.append(batchInfo);
}

// ====== 更新分段進度條 ======
function updateSegmentedProgress(progressBarId, current, total, message = '', batchInfo = '') {
    const segments = $(`#${progressBarId} .progress-segment`);
    
    // 確保 current 和 total 都有有效值
    current = parseInt(current) || 0;
    total = parseInt(total) || segments.length;
    
    console.log(`更新進度: current=${current}, total=${total}`);
    
    // 更新分段狀態 - 填充已完成的批次
    segments.each(function(index) {
        const segment = $(this);
        
        if (index < current) {
            // 已完成的分段 - 填滿
            segment.removeClass('processing').addClass('filled');
        } else if (index === current && current < total) {
            // 當前正在處理的分段 - 顯示處理動畫
            segment.removeClass('filled').addClass('processing');
        } else {
            // 還未處理的分段 - 保持空白
            segment.removeClass('filled processing');
        }
    });
    
    // 更新進度文字
    const progressText = $(`#${progressBarId}-text`);
    if (progressText.length && message) {
        progressText.text(message);
    }
    
    // 更新批次信息
    const batchInfoElement = $(`#${progressBarId}-batch`);
    if (batchInfoElement.length && batchInfo) {
        batchInfoElement.text(batchInfo);
    }
}

// ====== 測試進度條功能 ======
function testProgressBar() {
    createSegmentedProgressBar('feedback-progress', 7);
    let current = 0;
    const total = 7;
    
    const interval = setInterval(() => {
        current++;
        updateSegmentedProgress(
            'feedback-progress', 
            current, 
            total, 
            `處理批次 ${current}/${total}`, 
            `正在評估 Persona...`
        );
        
        if (current >= total) {
            clearInterval(interval);
            setTimeout(() => {
                updateSegmentedProgress(
                    'feedback-progress', 
                    total, 
                    total, 
                    '評估完成！', 
                    '所有批次已處理完成'
                );
            }, 1000);
        }
    }, 2000);
}