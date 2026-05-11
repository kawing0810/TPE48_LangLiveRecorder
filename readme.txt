TPE48 LangLiveRecorder
======================================

本文件最後更新：2026-05-05（文件版本與下方「目前標示版本」同步維護）

--------------------------------------
目前標示版本（建議對外／對內溝通）
--------------------------------------
- 產品線名稱：TPE48 LangLiveRecorder
- 發展代號：Alpha 4 → Alpha 5（穩定性與發版流程為主軸）
- 建議程式版本字串：4.5.0-alpha（開發中工作區；尚未固定 Git tag 時請以 commit 為準）
- 已知 Git 標籤：
  - v4.4.0-alpha.1-test（測試用 Release workflow／請勿視為正式版）

查證方式（本機）：
> git describe --tags --always
> git log -5 --oneline


--------------------------------------
版本編號說明（本專案約定）
--------------------------------------
主版本.次版本.修補[-後綴]
- 主版本：大方向或不相容變更（例如錄影流程或設定檔結構大改）
- 次版本：新功能或中型改良（UI、gate、CI）
- 修補：錯誤修正或小調整
- 後綴：alpha / rc / test 等預發布標記

GitHub Release 資產命名請沿用既有 workflow：
  dist/TPE48_LangLiveRecorder_${TAG}.zip


--------------------------------------
專案說明
--------------------------------------
自動偵測 Lang Live 成員是否開播，並以 ffmpeg 錄製直播；並附本機監控／控制台與品質驗收工具。

主要流程：
1) Checker（ttp_checker.py）依 members.json 輪詢
2) 發現開播後啟動 Recorder（ttp_recorder.py）
3) Recorder 使用 ffmpeg 錄影，並寫入 data/ 狀態與歷史
4) 儀表板（網頁或 Tkinter）顯示快照與歷史


--------------------------------------
環境需求
--------------------------------------
- Windows（主要使用情境）
- Python 3（建議 3.9+；CI 以 3.11 驗證）
- ffmpeg / ffprobe（建議放在專案根目錄，或系統 PATH 可執行）


--------------------------------------
設定檔（config.json）
--------------------------------------
集中設定錄影穩定性、重試與 Alpha 5 gate 門檻；Tkinter「設定」分頁可編輯後儲存。

主要區塊：
- recorder.*：卡住判定、重啟上限、最短分段、退避參數等
- alpha5_gate.*：升版驗收門檻（成功率、平均重啟、短片段比例等）
- monthly_quality.*：月度品質報告門檻（若存在）

詳細鍵名請直接開啟 config.json 對照。


--------------------------------------
啟動方式（批次檔）
--------------------------------------
1) 主監控（預設群組）
> run.bat

2) other 群組監控
> other.bat

3) 手動錄製單一成員（另開視窗執行 recorder）
> record.bat {langlive_id}

4) 互動輸入 UID 錄製
> adhoc.bat

5) 錄畫模式 MVP 小窗（同機整合輸入／啟停／內嵌 log；開發中）
> record_mvp.bat

6) 本機網頁儀表板
> dashboard.bat
瀏覽器： http://127.0.0.1:8787

7) Tkinter 監控控制台（確認君向：監控總覽、設定頁等）
> tkinter_dashboard.bat


--------------------------------------
Watchdog（Windows 排程）
--------------------------------------
> create_watchdog.bat    （約每 5 分鐘檢查 checker）
> remove_watchdog.bat

注意：create_watchdog.bat 會呼叫 watchdog.vbs，請確認檔案存在。


--------------------------------------
輸出與狀態檔案
--------------------------------------
- 錄影檔：{uid}Y_YYMMDD_HH_MM_SS.ts
- 封面：liveimg/（檔名含 _liveimg）
- data/dashboard_state.json       Checker 快照
- data/active_recordings.json     錄影中狀態
- data/recording_history.json     錄影歷史（含失敗分類等）
- data/liveimg_cache.json         封面 URL 去重快取
- data/reports/quality-YYYY-MM.md 月度品質報告（若執行報告腳本）


--------------------------------------
品質驗收與報告
--------------------------------------
Alpha 5 Gate（預設讀取 config.json 中 alpha5_gate）：
> python alpha5_gate.py

月度品質報告（預設讀取 config.json 中 monthly_quality，若無則用內建預設）：
> python monthly_quality_report.py --year 2026 --month 4

單元測試：
> python -m unittest discover -s tests -p "test_*.py"


--------------------------------------
CI / Release（GitHub Actions）
--------------------------------------
- .github/workflows/python-ci.yml
  push / pull_request：語法檢查、gate smoke、單元測試
- .github/workflows/release.yml
  push tag v*：打包 zip 並建立 GitHub Release
- .github/workflows/monthly-quality-report.yml
  排程或手動：產出月度報告 artifact（範例環境可能使用空歷史）

發版節奏與回滾流程摘要：docs/release_train.md


======================================
變更日誌（CHANGELOG）
======================================

说明：下列版本號為「專案對外文件版本」；若與 Git tag 並存，以 tag 為發版依據。
未列 commit 的條目代表「工作區／後續提交預計納入之下一版」，請以實際 git 為準。

--------------------------------------
[未發布／開發中] 4.5.0-alpha（預計）
--------------------------------------
- 錄畫模式 MVP：`record_mvp_launcher.py` + `record_mvp.bat`（單場錄影小窗、內嵌 recorder 輸出、檔案大小／秒數更新）
- Checker 快照：`last_live_at`（上次開播偵測時間）供監控 UI 使用
- Tkinter「監控總覽」：開播優先、新開播提示（可選音效）、Checker 間隔顯示
- 模組化：`recorder_core.py`（失敗分類、退避、參數正規化）
- 測試：`tests/test_recorder_core.py`、`tests/test_alpha5_gate.py`
- 月度品質報告：`monthly_quality_report.py`、`config.json` 可含 monthly_quality
- 文件：`docs/release_train.md`

--------------------------------------
[CI／設定整合] 4.4.x — 對應 commit 3a4867a
--------------------------------------
標題：add configurable stability settings and release automation

重點：
- config.json：recorder 與 alpha5_gate 參數外部化
- ttp_recorder.py：啟動時套用 config 之錄影參數
- alpha5_gate.py：門檻可由 config 覆寫（含 max_short_ratio）
- tkinter_dashboard.py：設定分頁（重載／儲存／還原預設）
- readme：補充設定與 CI／Release 說明
- GitHub Actions：python-ci.yml、release.yml（zip 資產）

--------------------------------------
[基線] 4.2.0 — 對應 commit 558a79e
--------------------------------------
標題：Initialize Alpha 4.2 baseline with stability tooling.

重點：
- 建立可發版／可維運基線（含 stability 相關工具與文件取向）
- 後續在此之上疊加 config、workflow、gate 與桌面 UX


--------------------------------------
[測試標籤] v4.4.0-alpha.1-test
--------------------------------------
- 用途：驗證 GitHub Release workflow（附件 zip）
- 非正式穩定版；請勿直接當作「正式對外版本號」唯一依據


--------------------------------------
Alpha 4 功能總覽（橫跨多個小版本累積）
--------------------------------------
- 本機監控儀表板（中文介面、控制台風格）
- 手動錄影／停止、成員頭像（優先 liveimg，其次 avatar）
- 直播封面下載至 liveimg/，同一 URL 不重複下載
- 錄影歷史：成功／失敗、時長、結束時間、輸出檔、失敗分類等
- 錄影結果檢查（範例）：有聲無畫、無畫面、開頭無音訊等視為失敗（規則以 ttp_recorder.py 為準）
- 卡住偵測與重啟策略（參數見 config.json）
- Alpha 5 Gate 腳本：alpha5_gate.py


--------------------------------------
舊版紀錄（簡述）
--------------------------------------
Alpha 3.1 (約 2022/03/29)
- m3u8 URL 含 query string 時，嘗試改寫為 HD 路徑

Alpha 3 (約 2021/07/14)
- watchdog 排程檢查
- 關閉終端 quick edit 以降低卡住
- 視窗標題 TTP {langlive_id} 降低重複錄影誤判
- room info 查詢加入 timeout


--------------------------------------
授權與責任聲明
--------------------------------------
請遵守 Lang Live／相关内容提供者的使用條款與著作權規範；本工具僅為技術輔助，請於合法與授權範圍內使用。
