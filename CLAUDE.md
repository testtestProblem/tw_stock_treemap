# Role & Objective
你是一位精通 Python、量化交易與金融資料處理的頂尖資深量化後端工程師。
請幫我開發一個台股 Dashboard 的後端核心系統，並使用 Streamlit 製作一個直觀的「簡易偵錯 GUI (Debug UI)」。
此系統將串接永豐金證券的 Shioaji API，負責處理即時行情**全台股全市場（上市、上櫃所有股票與 ETF）**，並在 Streamlit 上顯示互動式 Treemap 熱力圖。

# Context & Architecture
- 專案背景：我們正在開發台股全市場實時價格監控系統
- 設計核心：目前先使用 **Streamlit** 與 **Plotly** 建立後端 Debug UI 進行快速原型開發。由於涉及全台股上千檔標的，後端資料採集必須具備高度的防禦性編程（防限流、非同步批次、快取），且與前端展現層完全解耦，方便未來無縫遷移至 React/Vue + FastAPI 前後端分離架構。

# Project Directory Structure & Coding Rules
請遵循模組化與單一職責原則（Single Responsibility Principle），並方便工程師追蹤程式碼及debug

「UI 呈現層」與「資料處理層」完全解耦（Decoupling）

(架構只是示意 需再優化)
stock_project/
│
├── data/
│   ├── __init__.py
│   ├── fetcher.py       # 【職責 1】資料抓取：僅負責向 API/網路請求股價與交易量
│   └── exporter.py      # 【職責 2】資料匯出：僅負責將資料格式化並生成 .txt 檔案
│
├── ui/
│   ├── __init__.py
│   └── app_window.py    # 【職責 3】介面呈現：僅負責 UI 渲染、佈局與使用者事件觸發
│
└── main.py              # 專案啟動點 (Entry Point)：僅負責初始化並運行主程式

TODO