TTP Lang Live Recorder - Alpha 4
======================================

專案說明
--------------------------------------
此專案用於自動偵測 Lang Live 成員是否開播，並以 ffmpeg 錄製直播檔案。

主要流程：
1) checker 輪詢 members.json
2) 發現開播後啟動 recorder
3) recorder 以 ffmpeg 錄影
4) 儀表板顯示即時狀態與歷史結果


環境需求
--------------------------------------
- Windows
- Python 3
- ffmpeg / ffprobe（建議放在專案根目錄，或可由系統 PATH 直接執行）


啟動方式
--------------------------------------
1) 啟動主監控（預設群組）
> run.bat

2) 啟動 other 群組監控
> other.bat

3) 手動錄製單一成員
> record.bat {langlive_id}

4) 臨時手動輸入 ID 錄製
> adhoc.bat

5) 啟動本機監控儀表板
> dashboard.bat
開啟瀏覽器：
http://127.0.0.1:8787

6) 啟動 Tkinter 視窗控制台
> tkinter_dashboard.bat


Watchdog（Windows 排程）
--------------------------------------
- 建立 watchdog 任務（每 5 分鐘檢查 checker）
> create_watchdog.bat

- 移除 watchdog 任務
> remove_watchdog.bat

注意：create_watchdog.bat 會呼叫 watchdog.vbs，請確認檔案存在。


輸出檔案
--------------------------------------
- 錄影檔：{uid}Y_YYMMDD_HH_MM_SS.ts
- 封面檔：liveimg/{uid}Y_YYMMDD_HH_MM_SS_liveimg.xxx
- 狀態檔：
  - data/dashboard_state.json（checker 快照）
  - data/active_recordings.json（錄影中）
  - data/recording_history.json（錄影歷史）
  - data/liveimg_cache.json（封面 URL 去重快取）


Alpha 4 新增重點
--------------------------------------
- 新增本機監控儀表板（中文 + 控制台風格）
- 儀表板支援手動操作：
  - 立即錄影
  - 停止指定錄影
- 儀表板顯示成員頭像（優先 liveimg，其次 avatar）
- 每場錄影可下載直播封面 liveimg 到 liveimg/ 子資料夾
- 封面去重：同一 URL 不重複下載
- 新增錄影歷史清單（成功/失敗、時長、結束時間、輸出檔）
- 新增錄影結果檢查：
  - 有聲無畫 => 失敗
  - 無畫面 => 失敗
  - 開頭無音訊（疑似開場異常）=> 失敗
  - 有畫面且音訊正常 => 成功
- 新增 Alpha 5 升版驗收腳本：
  > python alpha5_gate.py
  （預設檢查最近 3 天：成功率、平均重啟次數、短片段比例）


舊版本紀錄
--------------------------------------
Alpha 3.1 (2022/03/29)
- m3u8 URL 含 query string 時，嘗試改寫為 HD 路徑

Alpha 3 (2021/07/14)
- 新增 watchdog 排程檢查
- 新增 quick edit 關閉以避免終端卡住
- 以視窗標題 TTP {langlive_id} 避免重複錄影
- room info 查詢加入 timeout
