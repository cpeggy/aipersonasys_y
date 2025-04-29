// ====== Global Variables ======
let savedPersonas = [];
const APP_VERSION = Date.now();

$(document).ready(function() {
    console.log("應用程序初始化 v" + APP_VERSION);
    initializeApp();
    setupEventListeners();
    loadSavedPersonas();
});

// ====== 初始化頁籤邏輯 ======
function initializeApp() {
    console.log("初始化 Bootstrap 5 Tab");
    const hash = window.location.hash;
    if (hash) {
        const tabEl = document.querySelector(`a[data-bs-target="${hash}"]`);
        if (tabEl) new bootstrap.Tab(tabEl).show();
    } else {
        const defaultTabEl = document.querySelector('a[data-bs-target="#generate-tab"]');
        if (defaultTabEl) new bootstrap.Tab(defaultTabEl).show();
    }
}

// 處理頁籤切換邏輯
function setupTabNavigation() {
    // 為導航項目添加點擊事件
    $('#nav-generate').click(function() {
        switchToTab('generate-tab');
    });
    
    $('#nav-feedback').click(function() {
        switchToTab('feedback-tab');
    });
    
    $('#nav-saved').click(function() {
        switchToTab('saved-personas-tab');
    });
    
    // 設置初始頁籤（預設為生成頁籤）
    switchToTab('generate-tab');
}

// 切換到指定頁籤
function switchToTab(tabId) {
    // 隱藏所有頁籤
    $('.tab-pane').hide();
    
    // 顯示目標頁籤
    $(`#${tabId}`).show();
    
    // 更新導航項目的活動狀態
    $('.navbar-nav .nav-link').removeClass('active');
    
    // 根據 tabId 設置對應的導航項目為活動狀態
    if (tabId === 'generate-tab') {
        $('#nav-generate').addClass('active');
    } else if (tabId === 'feedback-tab') {
        $('#nav-feedback').addClass('active');
    } else if (tabId === 'saved-personas-tab') {
        $('#nav-saved').addClass('active');
    }
}

// 在文件加載完成後初始化
$(document).ready(function() {
    console.log("應用程序初始化 v" + APP_VERSION);
    
    // 設置頁籤導航
    setupTabNavigation();
    
    // 其他初始化代碼
    setupEventListeners();
    loadSavedPersonas();
});

// ====== 設定各種按鈕事件 ======
function setupEventListeners() {
    // 表單提交事件
    $('#csv-form').on('submit', e => { e.preventDefault(); processCSVForm(); });
    $('#md-form').on('submit', e => { e.preventDefault(); processMDForm(); });
    $('#feedback-form').on('submit', e => { e.preventDefault(); processFeedbackForm(); });
    $('#refresh-personas').on('click', loadSavedPersonas);
    // 添加新的綁定
    $('#csv2-form').on('submit', e => { e.preventDefault(); processCSV2Form(); });
    // 導航項目點擊事件 - 加入這個部分
    $('#nav-generate').on('click', function() {
        $('.tab-pane').hide();
        $('#generate-tab').show();
        $('.navbar-nav .nav-link').removeClass('active');
        $(this).addClass('active');
    });
    
    $('#nav-feedback').on('click', function() {
        $('.tab-pane').hide();
        $('#feedback-tab').show();
        $('.navbar-nav .nav-link').removeClass('active');
        $(this).addClass('active');
    });
    
    $('#nav-saved').on('click', function() {
        $('.tab-pane').hide();
        $('#saved-personas-tab').show();
        $('.navbar-nav .nav-link').removeClass('active');
        $(this).addClass('active');
    });
    
    // 原有的 Bootstrap 頁籤事件仍保留，但可能不會被觸發
    document.querySelectorAll('a[data-bs-toggle="tab"]').forEach(tabEl => {
        tabEl.addEventListener('shown.bs.tab', function () {
            window.location.hash = this.getAttribute('data-bs-target').substring(1);
        });
    });
}

// ====== 上傳 CSV 處理 ======
function processCSVForm() {
    const fileInput = $('#csv-file')[0];
    if (fileInput.files.length === 0) return alert('請選擇 CSV 檔案');

    $('#csv-progress').removeClass('d-none');
    $('#csv-submit').prop('disabled', true);
    $('#csv-result').addClass('d-none'); // 先隱藏結果區域

    const formData = new FormData();
    formData.append('csv_file', fileInput.files[0]);

    $.ajax({
        url: '/process-csv',
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: function(response) {
            $('#csv-progress').addClass('d-none');
            $('#csv-submit').prop('disabled', false);
            
            console.log("處理 CSV 成功，伺服器回應:", response);
            
            if (response.success) {
                // 更新 persona 數量
                $('#csv-persona-count').text(response.persona_count);
                
                // 更新下載連結
                if (response.zip_path) {
                    $('#csv-download-zip').attr('href', `/download/${response.zip_path}`);
                }
                if (response.csv_log_path) {
                    $('#csv-download-log').attr('href', `/download/${response.csv_log_path}`);
                }
                
                // 顯示結果區域
                $('#csv-result').removeClass('d-none');
                
                // 更新 persona 選擇列表
                if (response.personas && response.personas.length > 0) {
                    savedPersonas = response.personas;
                    updatePersonaSelections();
                } else {
                    console.warn("回應中沒有 personas 資料或為空陣列");
                }
            } else {
                alert('處理成功但回應格式異常，請檢查控制台');
                console.error("回應格式不符合預期:", response);
             // 檢查是否有批次信息
            let batchInfo = "";
            if (response.personas && response.personas.length > 0 && response.personas[0].batch_info) {
                const batches = new Set(response.personas.map(p => p.batch_info));
                batchInfo = `<div class="alert alert-info mt-2">
                    <small>透過批次處理技術完成，共 ${batches.size} 個批次</small>
                </div>`;
                $('#csv-result').append(batchInfo);
            }
            }
        },
        error: function(xhr) {
            $('#csv-progress').addClass('d-none');
            $('#csv-submit').prop('disabled', false);
            const errorMsg = xhr.responseJSON ? (xhr.responseJSON.error || xhr.statusText) : xhr.statusText;
            alert('處理失敗: ' + errorMsg);
            console.error("處理 CSV 錯誤:", xhr.responseJSON || xhr.statusText);
        }
    });
}
// ====== 上傳 CSV2 處理 ======
function processCSV2Form() {
    const fileInput = $('#csv2-file')[0];
    if (fileInput.files.length === 0) return alert('請選擇 CSV 檔案');

    $('#csv2-progress').removeClass('d-none');
    $('#csv2-submit').prop('disabled', true);
    $('#csv2-result').addClass('d-none'); // 先隱藏結果區域

    const formData = new FormData();
    formData.append('csv_file', fileInput.files[0]);
    // 添加一個識別標記，告訴後端這是第二種類型的 CSV
    formData.append('csv_type', 'type2');

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
                if (response.zip_path) {
                    $('#csv2-download-zip').attr('href', `/download/${response.zip_path}`);
                }
                if (response.csv_log_path) {
                    $('#csv2-download-log').attr('href', `/download/${response.csv_log_path}`);
                }
                
                // 顯示結果區域
                $('#csv2-result').removeClass('d-none');
                
                // 更新 persona 選擇列表
                if (response.personas && response.personas.length > 0) {
                    savedPersonas = response.personas;
                    updatePersonaSelections();
                } else {
                    console.warn("回應中沒有 personas 資料或為空陣列");
                }
            } else {
                alert('處理成功但回應格式異常，請檢查控制台');
                console.error("回應格式不符合預期:", response);
            }
        },
        error: function(xhr) {
            $('#csv2-progress').addClass('d-none');
            $('#csv2-submit').prop('disabled', false);
            const errorMsg = xhr.responseJSON ? (xhr.responseJSON.error || xhr.statusText) : xhr.statusText;
            alert('處理失敗: ' + errorMsg);
            console.error("處理 CSV2 錯誤:", xhr.responseJSON || xhr.statusText);
        }
    });
}
// ====== 上傳 MD 處理 ======
function processMDForm() {
    console.log("MD處理開始");
    const fileInput = $('#md-files')[0];
    
    if (fileInput.files.length === 0) {
        alert('請選擇至少一個 MD 檔案');
        return;
    }
    
    // 顯示處理中狀態
    $('#md-progress').removeClass('d-none');
    $('#md-result').addClass('d-none');
    $('#md-submit').prop('disabled', true);
    
    // 建立表單資料
    const formData = new FormData();
    for (let i = 0; i < fileInput.files.length; i++) {
        console.log("添加檔案:", fileInput.files[i].name);
        formData.append('md_files[]', fileInput.files[i]);
    }

    $.ajax({
        url: '/process-md',
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: function(response) {
            // 隱藏進度條
            $('#md-progress').addClass('d-none');
            // 啟用提交按鈕
            $('#md-submit').prop('disabled', false);
            
            console.log("MD 處理成功，伺服器回應:", response);
            
            if (response.success) {
                // 更新生成的 persona 數量
                $('#md-persona-count').text(response.persona_count || 0);
                
                // 更新下載連結
                if (response.zip_path) {
                    $('#md-download-zip').attr('href', `/download/${response.zip_path}`);
                }
                
                if (response.csv_log_path) {
                    $('#md-download-log').attr('href', `/download/${response.csv_log_path}`);
                }
                
                // 顯示結果區域
                $('#md-result').removeClass('d-none');
                
                // 更新 persona 選擇列表
                if (response.personas && response.personas.length > 0) {
                    savedPersonas = response.personas;
                    updatePersonaSelections();
                    
                    // 顯示成功訊息
                    alert(`成功生成 ${response.persona_count} 個 Personas！`);
                } else {
                    console.warn("回應中沒有 personas 資料或為空陣列");
                }
            } else {
                alert('處理成功但回應格式異常，請檢查控制台');
                console.error("回應格式不符合預期:", response);
            }
        },
        error: function(xhr) {
            // 隱藏進度條
            $('#md-progress').addClass('d-none');
            // 啟用提交按鈕
            $('#md-submit').prop('disabled', false);
            
            const errorMsg = xhr.responseJSON ? (xhr.responseJSON.error || xhr.statusText) : xhr.statusText;
            alert('處理失敗: ' + errorMsg);
            console.error("處理 MD 錯誤:", xhr.responseJSON || xhr.statusText);
        }
    });
}

// ====== Feedback 評估表單處理 + 畫圖 ======
function processFeedbackForm() {
    const selectedPersonas = $('.persona-checkbox:checked').map(function() { return $(this).val(); }).get();
    const marketingCopy = $('#marketing-copy').val().trim();

    if (selectedPersonas.length === 0) return alert('請至少選一個 Persona');
    if (!marketingCopy) return alert('請輸入行銷文案');

    $('#feedback-progress').removeClass('d-none');
    $('#feedback-submit').prop('disabled', true);
    $('#feedback-result').addClass('d-none'); // 先隱藏結果區域

    const data = { selected_personas: selectedPersonas, marketing_copy: marketingCopy };

    $.ajax({
        url: '/process-feedback',
        type: 'POST',
        data: JSON.stringify(data),
        contentType: 'application/json',
        success: function(response) {
            $('#feedback-progress').addClass('d-none');
            $('#feedback-submit').prop('disabled', false);
            
            console.log("評估回應:", response); // 記錄回應以便調試
            
            if (response.success) {
                // 顯示結果區域
                $('#feedback-result').removeClass('d-none');
                
                // 處理圖表
                if (response.chart) {
                    $('#score-chart').attr('src', 'data:image/png;base64,' + response.chart);
                } else {
                    $('#score-chart').html('<div class="alert alert-warning">無法生成圖表</div>');
                }
                
                // 處理購買理由
                let buyReasons = '<ul class="list-group">';
                if (response.feedback && response.feedback.length > 0) {
                    // 收集所有購買理由
                    const allBuyReasons = [];
                    response.feedback.forEach(item => {
                        if (item.reasons_to_buy && item.reasons_to_buy.length > 0) {
                            allBuyReasons.push(...item.reasons_to_buy);
                        }
                    });
                    
                    // 顯示收集到的購買理由
                    if (allBuyReasons.length > 0) {
                        allBuyReasons.forEach(reason => {
                            buyReasons += `<li class="list-group-item">${reason}</li>`;
                        });
                    } else {
                        buyReasons += '<li class="list-group-item">沒有購買理由</li>';
                    }
                } else {
                    buyReasons += '<li class="list-group-item">沒有評估資料</li>';
                }
                buyReasons += '</ul>';
                $('#buy-reasons').html(buyReasons);
                
                // 處理不購買理由
                let notBuyReasons = '<ul class="list-group">';
                if (response.feedback && response.feedback.length > 0) {
                    // 收集所有不購買理由
                    const allNotBuyReasons = [];
                    response.feedback.forEach(item => {
                        if (item.reasons_not_to_buy && item.reasons_not_to_buy.length > 0) {
                            allNotBuyReasons.push(...item.reasons_not_to_buy);
                        }
                    });
                    
                    // 顯示收集到的不購買理由
                    if (allNotBuyReasons.length > 0) {
                        allNotBuyReasons.forEach(reason => {
                            notBuyReasons += `<li class="list-group-item">${reason}</li>`;
                        });
                    } else {
                        notBuyReasons += '<li class="list-group-item">沒有不購買理由</li>';
                    }
                } else {
                    notBuyReasons += '<li class="list-group-item">沒有評估資料</li>';
                }
                notBuyReasons += '</ul>';
                $('#not-buy-reasons').html(notBuyReasons);
                
                // 處理各 Persona 詳細評估
                let personaCards = '';
                if (response.feedback && response.feedback.length > 0) {
                    response.feedback.forEach(item => {
                        // 決定分數顏色
                        let scoreClass = 'bg-danger';
                        if (item.score >= 8) scoreClass = 'bg-success';
                        else if (item.score >= 6) scoreClass = 'bg-primary';
                        else if (item.score >= 4) scoreClass = 'bg-warning';
                        
                        personaCards += `
                            <div class="col-md-6 mb-3">
                                <div class="card persona-feedback-card">
                                    <div class="card-header d-flex justify-content-between align-items-center">
                                        <h6 class="mb-0">Persona ${item.persona_id}</h6>
                                        <span class="badge ${scoreClass} score-badge">${item.score} / 10</span>
                                    </div>
                                    <div class="card-body">
                                        <div class="mb-3">
                                            <h6 class="text-success"><i class="fas fa-thumbs-up"></i> 購買理由：</h6>
                                            <ul class="reasons-list">
                                                ${item.reasons_to_buy && item.reasons_to_buy.length > 0 ? 
                                                    item.reasons_to_buy.map(reason => `<li>${reason}</li>`).join('') : 
                                                    '<li>無明確購買理由</li>'}
                                            </ul>
                                        </div>
                                        <div>
                                            <h6 class="text-danger"><i class="fas fa-thumbs-down"></i> 不購買理由：</h6>
                                            <ul class="reasons-list">
                                                ${item.reasons_not_to_buy && item.reasons_not_to_buy.length > 0 ? 
                                                    item.reasons_not_to_buy.map(reason => `<li>${reason}</li>`).join('') : 
                                                    '<li>無明確不購買理由</li>'}
                                            </ul>
                                        </div>
                                        <button class="btn btn-sm btn-outline-secondary mt-2" 
                                                data-bs-toggle="modal" 
                                                data-bs-target="#feedbackModal" 
                                                data-feedback="${encodeURIComponent(item.detail_feedback)}"
                                                data-persona="${item.persona_id}">
                                            查看完整評估
                                        </button>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                } else {
                    personaCards = '<div class="col-12"><div class="alert alert-info">沒有評估資料</div></div>';
                }
                $('#persona-feedback-cards').html(personaCards);
                
                // 確保有完整評估的對話框
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
            } else {
                alert('評估失敗: ' + (response.error || '未知錯誤'));
            }
        },
        error: function(xhr) {
            $('#feedback-progress').addClass('d-none');
            $('#feedback-submit').prop('disabled', false);
            const errorMsg = xhr.responseJSON ? (xhr.responseJSON.error || xhr.statusText) : xhr.statusText;
            alert('評估失敗: ' + errorMsg);
            console.error("評估錯誤:", xhr.responseJSON || xhr.statusText);
        }
    });
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

// ====== 載入本地已儲存 Persona ======
function loadSavedPersonas() {
    console.log("載入儲存 Persona");
    $.ajax({
        url: '/load-personas',
        type: 'GET',
        success: function(response) {
            console.log("載入到的 personas 數量:", response.personas ? response.personas.length : 0);
            console.log("persona IDs:", response.personas ? response.personas.map(p => p.persona_id) : []);
            
            if (response.personas) {
                savedPersonas = response.personas;
                updatePersonaSelections();
            }
        },
        error: function(xhr) {
            console.error("載入 Persona 失敗:", xhr);
        }
    });
}

// ====== 更新 Persona 選擇清單 ======
function updatePersonaSelections() {
    const container = $('#persona-selection');
    container.empty();

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