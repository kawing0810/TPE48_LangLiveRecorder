TPE48 LangLiveRecorder
======================================

本文件最後更新：2026-06-24

--------------------------------------
專案定位
--------------------------------------
TPE48 LangLiveRecorder 用於監控 Lang Live 開播狀態，並透過 ffmpeg 錄製直播內容，
同時提供本機儀表板、Tk 控制台、品質驗收與發版自動化流程。

核心流程：
1) Checker 讀取 members 名單並輪詢直播狀態
2) 發現開播時啟動 Recorder
3) Recorder 寫入錄影檔與歷史資料
4) Dashboard / Tkinter 顯示即時快照與操作入口


--------------------------------------
目前版本與追蹤方式
--------------------------------------
- 建議版本字串：4.5.3-alpha（開發線）
- 建議 Git tag：v4.5.3-alpha
- 目前主要分支：alpha5-dev
- 正式發版基底：master

本機查詢：
> git describe --tags --always
> git log --oneline -10


--------------------------------------
環境需求
--------------------------------------
- Windows（主要運行平台）
- Python 3.9+（CI 使用 3.11）
- ffmpeg / ffprobe（可放專案根目錄或加入 PATH；ffprobe 為錄影中 A/V 即時檢查所需）


--------------------------------------
主要檔案
--------------------------------------
- ttp_checker.py：輪詢與啟動錄影器
- ttp_recorder.py：錄影主流程、卡住重啟、錄影結果驗證
- recorder_core.py：失敗分類、退避、參數正規化（可測試邏輯）
- dashboard.py：本機 Web 儀表板
- tkinter_dashboard.py：桌面控制台（監控總覽、設定、操作）
- alpha5_gate.py：品質門檻檢查腳本
- monthly_quality_report.py：月度品質報告輸出


--------------------------------------
設定檔（config.json）
--------------------------------------
集中管理錄影穩定性與品質門檻，主要區塊如下：

- recorder.*：卡住秒數、重啟上限、分段與退避策略、output_mode（remux/copy）、max_av_duration_gap_seconds
- alpha5_gate.*：升版檢查門檻
- monthly_quality.*：月報門檻設定

Tkinter 控制台可直接載入、編輯、驗證與儲存設定。


--------------------------------------
啟動方式（批次檔）
--------------------------------------
1) 主監控（預設群組）
> run.bat

2) other 群組監控
> other.bat

3) 手動錄製單一成員
> record.bat {langlive_id}

4) 互動式輸入 UID 錄製
> adhoc.bat

5) 錄畫模式 MVP（快速手錄小窗）
> record_mvp.bat

6) Web 儀表板
> dashboard.bat
瀏覽器： http://127.0.0.1:8787

7) Tkinter 控制台
> tkinter_dashboard.bat


--------------------------------------
輸出資料
--------------------------------------
- 錄影檔：{uid}Y_YYMMDD_HH_MM_SS.ts（stall 重啟會產生新檔，同秒重啟可能帶 _rN 後綴）
- 封面：liveimg/*_liveimg.*
- 快照：data/dashboard_state.json
- 錄影中：data/active_recordings.json
- 錄影歷史：data/recording_history.json
- 封面快取：data/liveimg_cache.json
- 月報輸出：data/reports/quality-YYYY-MM.md


--------------------------------------
品質驗收與測試
--------------------------------------
Alpha 5 gate：
> python alpha5_gate.py

指定期間 gate：
> python alpha5_gate.py --days 7 --min-records 10

月度品質報告：
> python monthly_quality_report.py --year 2026 --month 5

單元測試：
> python -m unittest discover -s tests -p "test_*.py"


--------------------------------------
CI / Release（GitHub Actions）
--------------------------------------
- .github/workflows/python-ci.yml
  - 語法檢查
  - gate smoke
  - tests/* 單元測試

- .github/workflows/release.yml
  - 推送 tag（v*）後建立 Release 與 zip 資產

- .github/workflows/monthly-quality-report.yml
  - 排程或手動產出月度品質報告 artifact


--------------------------------------
發版策略（摘要）
--------------------------------------
- master：可發版主幹
- alpha5-dev：整合與迭代分支
- feature/*：短生命週期分支，合併前需通過 CI
- tag：v主版.次版.修補[-alpha.N]

完整發版節奏與回滾流程請見：
docs/release_train.md


--------------------------------------
近期版本重點（4.5.3-alpha）
--------------------------------------
- 錄影中每 3 秒 ffprobe 檢查 A/V duration gap（超過 max_av_duration_gap_seconds 停段重啟）
- 連續 probe 僅有 audio、無 video 時立即停段（audio_only_probe_fail_count，預設 1）
- ffmpeg console 預設 loglevel error，隱藏 HLS 正常 EOF 警告；關閉 reconnect（與 m3u8 不相容）
- stall 重啟、結束驗證、probe 後備邏輯集中於 recorder_core.py

上一版（4.5.2-alpha）重點：
- stall 重啟一律新檔名，避免 -y 覆寫同一檔造成時間軸錯亂（畫面加速/後段無聲）
- 錄完驗證視訊/音訊 duration 差（max_av_duration_gap_seconds，預設 30 秒）
- 預設 stall 偵測 15 秒、開場 grace 5 秒（config.json 可調）
- 預設 remux 錄影（genpts、A/V map、mux 參數順序修正）
- 錄影決策邏輯模組化（recorder_core.py、output_mode 設定）
- Gate / 月報與 CI 串接
- 測試基礎建立（test_recorder_core.py / test_alpha5_gate.py）

上一版（4.5.1-alpha）重點：
- remux 長場錄影實測通過（播放順暢、聲畫同步）
- 錄畫模式 MVP（record_mvp_launcher.py）
- 監控總覽優化（新開播提示、排序、狀態可讀性）


--------------------------------------
Watchdog（Windows 排程）
--------------------------------------
建立：
> create_watchdog.bat

移除：
> remove_watchdog.bat


--------------------------------------
授權與使用提醒
--------------------------------------
請遵守平台條款與著作權規範。本工具僅用於合法授權範圍內的錄製與維運用途。
