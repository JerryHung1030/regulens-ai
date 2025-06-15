## 1 | 產品概觀

Regulens-AI 是一款以 **PySide6** 打造的桌面 GUI 應用，專注於法規遵循性審計。系統透過 LLM 與向量檢索技術，自動分析控制項（Controls）並生成審計計畫，協助使用者進行合規性評估。整體架構分為 **GUI 操作層** 與 **Pipeline 資料處理層** 兩大部分。

---

## 2 | 啟動與初始化流程

1. **main.py**
   * 載入自訂字體並設定全域字體
   * 讀取 `config_default.yaml`（或使用者覆寫版本）
   * 初始化翻譯器 → 多語系資源載入
   * 根據設定套用 **系統 / 淺色 / 深色** 主題
2. 建立 `MainWindow` → 顯示
3. 將上一次視窗大小、分割條位置與主題偏好自動還原

---

## 3 | GUI 結構總覽

### 3.1  主視窗 (MainWindow)

* **選單列**
  * `File → Settings…`　`Ctrl+,`
  * `File → Quit`　　　`Ctrl+Q`
* **多語言切換**：即時刷新所有 UI 文本

### 3.2  工作區 (Workspace)

* **QSplitter** 左右分割
  * **左側 Sidebar**：專案列表
  * **右側 StackedWidget**：內容區
* 分割比例可拖曳調整並自動記憶

### 3.3  主要頁面

| 頁面                | 作用                  |
| ----------------- | ------------------- |
| **ProjectEditor** | 編輯專案基本資訊、設定資料夾、啟動比較 |
| **ResultsViewer** | 顯示比較結果；可返回編輯器重新執行   |

---

## 4 | 專案管理

* **新增**：自動命名「Project 1 / 2 / …」
* **側邊欄**：點擊切換、右鍵刪除或重新命名
* **自動保存**：專案 JSON 直接寫入配置檔，關閉程式不遺失

---

## 5 | Pipeline 五大處理階段

> 由 `app/pipeline/pipeline_v1_1.py` 與相關模組實作

1. **初始化與載入**
   * 讀取控制項 JSON 檔案
   * 載入或初始化 `run.json`
   * 建立快取與輸出目錄

2. **需求檢查 (Need-Check)**
   * 分析每個控制項是否需要審計程序
   * 使用 LLM 評估控制項的複雜度
   * 更新 `run.json` 中的需求狀態

3. **審計計畫生成 (Audit Plan)**
   * 為需要審計的控制項生成審計任務
   * 使用 LLM 分解控制項為具體審計步驟
   * 更新 `run.json` 中的審計計畫

4. **證據搜尋 (Search)**
   * 讀取程序與證據文件
   * 生成文件向量嵌入
   * 建立 FAISS 索引
   * 檢索相關證據

5. **評估與判斷 (Judge)**
   * 使用 LLM 評估證據與控制項的符合度
   * 計算整體合規狀態
   * 生成詳細評估報告

---

## 6 | LLM 評估機制

### 6.1  評估層級

* **Need-Check**：評估控制項是否需要審計程序
* **Audit Plan**：生成具體審計任務
* **Judge**：評估證據與控制項的符合度

### 6.2  狀態與分數

| 狀態           | 說明   |
| ------------ | ---- |
| Pass         | 完全符合 |
| Partial      | 部分符合 |
| Fail         | 不符合  |
| Inconclusive | 證據不足 |
| NoEvidence   | 無證據  |

* 置信度 0.0–1.0，由 LLM 回傳
* 同一配對多筆評分 → 取平均作為整體分數

### 6.3  聚合規則

1. **Fail** 優先 → 任一 Fail，整體即 Fail
2. 否則如含 Partial → 整體 Partial
3. 全 Pass → 整體 Pass
4. 其餘 → Inconclusive

---

## 7 | 報告內容

1. **標題與簡介**
2. **各控制項分組結果**
   * 控制項原文
   * 審計計畫摘要
   * 整體狀態、得分、LLM 分析
   * 證據列表：狀態圖示 (✅⚠️❌❓)、片段、置信度、建議
3. **摘要分析**：聚合狀態 + 重點發現 (最多 3 條)

---

## 8 | 主題與樣式

* **系統跟隨** / **淺色** / **深色** 可即時切換
* QSS 承載字體、配色、圓角、間距
* 支援動態 Dark/Light 覆寫

---

## 9 | 多語言

* 透過 `Translator` 讀取 `.qm` 檔
* 切換語系時發送全域訊號，UI 文本即時更新

---

## 10 | 快取與效能

* 嵌入與評估結果寫入本地快取 → 重複運行節省 API 成本
* FAISS 索引分離存檔，支援增量更新
* 審計計畫與評估結果保存在 `run.json`

---

## 11 | 錯誤處理

* **API Error / JSONDecodeError / ValidationError** 皆捕獲並彈窗提示
* 記錄 log 檔供開發人員追蹤
* 比對流程中可 **取消**，並保留已完成部分結果

---

## 12 | 鍵盤快捷鍵

| 操作                 | 快捷鍵      |
| ------------------ | -------- |
| 開啟設定               | `Ctrl+,` |
| 退出程式               | `Ctrl+Q` |
| （其餘依 PySide6 預設行為） |          |

---

## 13 | 常見問題與排解

1. **啟動後畫面全白**
   * 檢查 `config_default.yaml` 是否缺漏主題設定
2. **無法產生嵌入**
   * 確認 OpenAI API Key 已在設定畫面填寫
3. **比較流程卡住**
   * 於進度面板點擊 "Cancel"；檢查 log 搜尋錯誤關鍵字

---

## 14 | 版本與相依

* **Python ≥ 3.10**
* **PySide6**（GUI）
* **faiss-cpu**（向量索引）
* **openai**（嵌入與 LLM）
* 其餘請參考 `requirements.txt`

---

### 連結到原始程式結構

```
regulens-ai/
├── app/                           # 主要應用程式目錄
│   ├── __init__.py               # 應用程式初始化
│   ├── main.py                    # 應用程式入口點
│   ├── mainwindow.py             # 主視窗類別
│   ├── settings_dialog.py        # 設定對話框
│   ├── settings.py               # 設定管理類別
│   ├── translator.py             # 多語言翻譯管理
│   ├── i18n.py                   # 國際化資源
│   ├── logger.py                 # 日誌記錄工具
│   │
│   ├── models/                   # 資料模型目錄
│   │   ├── project.py           # 專案資料模型
│   │   ├── docs.py              # 文件資料模型
│   │   ├── assessments.py       # 評估資料模型
│   │   └── settings.py          # 模型相關設定
│   │
│   ├── pipeline/                 # 處理管道目錄
│   │   ├── __init__.py          # 管道初始化
│   │   ├── pipeline_v1_1.py     # 主要處理流程
│   │   ├── ingestion.py         # 文件攝取處理
│   │   ├── normalize.py         # 文件正規化處理
│   │   ├── embed.py             # 向量嵌入生成
│   │   ├── index.py             # 向量索引建立
│   │   ├── retrieve.py          # 相似度檢索
│   │   ├── llm_utils.py         # LLM 工具函數
│   │   └── cache.py             # 快取管理
│   │
│   ├── views/                    # 視圖目錄
│   │   └── workspace.py         # 工作區視圖
│   │
│   ├── widgets/                  # 自定義元件目錄
│   │   ├── intro_page.py        # 介紹頁面元件
│   │   ├── project_editor.py    # 專案編輯器元件
│   │   ├── results_viewer.py    # 結果檢視器元件
│   │   ├── progress_panel.py    # 進度面板元件
│   │   └── sidebar.py           # 側邊欄元件
│   │
│   ├── stores/                   # 資料儲存目錄
│   │   └── project_store.py     # 專案資料儲存管理
│   │
│   └── utils/                    # 工具函數目錄
│       ├── theme_manager.py      # 主題管理工具
│       └── font_manager.py       # 字體管理工具
│
├── assets/                       # 資源檔案目錄
│   ├── themes/                   # 主題樣式檔案
│   └── fonts/                    # 字體檔案
│
├── tests/                        # 測試目錄
│   └── test_pipeline.py         # 管道測試
│
├── sample_data/                  # 範例資料目錄
│   ├── controls/                # 控制項範例
│   ├── procedures/              # 程序範例
│   └── evidences/               # 證據範例
│
├── output/                       # 輸出目錄
│   └── reports/                 # 生成的報告
│
├── cache/                        # 快取目錄
│   ├── indexes/                 # 向量索引快取
│   └── embeddings/              # 嵌入向量快取
│
├── logs/                         # 日誌目錄
│
├── .github/                      # GitHub 相關配置
│
├── requirements.txt              # Python 套件依賴
├── pyproject.toml               # 專案設定檔
├── config_default.yaml          # 預設設定檔
├── README.md                    # 專案說明文件
├── LICENSE                      # 授權文件
├── CONTRIBUTING.md              # 貢獻指南
├── .gitignore                   # Git 忽略檔案配置
├── clear.bat                    # Windows 清理腳本
└── clear.sh                     # Unix 清理腳本
```

---

> **至此，說明手冊完整覆蓋您提供的所有功能描述與程式模組，方便使用者快速上手與深入理解 Regulens-AI。**
