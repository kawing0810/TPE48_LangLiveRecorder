# Alpha Release Train / 回滾流程

## 分支策略

- `master`: 可發版分支，僅接受已通過 CI 的 PR。
- `alpha5-dev` / `alpha6-dev`: 版本整合分支。
- `feature/*`: 短生命週期功能分支，合併後刪除。
- `hotfix/*`: 緊急修補分支，合併到 `master` 後回灌整合分支。

## 月度發版節奏

- Week 1: 鎖定本月 scope（僅挑選已驗證工作）。
- Week 2: 合併功能與缺陷修正，維持 CI 全綠。
- Week 3: RC 標記測試（`vX.Y.Z-rc.N`）。
- Week 4: 正式 tag 發版（`vX.Y.Z`）並產出 release artifact。

## 發版前檢查

1. `python -m unittest discover -s tests -p "test_*.py"` 全部通過。
2. `python alpha5_gate.py` 結果 PASS（或經批准例外）。
3. `python monthly_quality_report.py --year YYYY --month M` 產出報告。
4. `readme.txt` 版本資訊與變更摘要已更新。

## 標準發版命令

1. 建立 tag：`git tag vX.Y.Z`
2. 推送 tag：`git push origin vX.Y.Z`
3. 確認 `Release` workflow 完成並含 zip artifact。

## 快速回滾

- 若發版後有重大問題：
  1. 使用 GitHub Revert PR 回退有問題的 PR。
  2. 建立 hotfix 分支補修。
  3. 發佈 `vX.Y.(Z+1)` hotfix 版本。
  4. 將 hotfix 回灌 `alpha*-dev`，避免分支漂移。