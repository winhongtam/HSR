# 交通時刻表參考

個人交通時刻表筆記，主要供 Claude 透過 GitHub 連接器查詢使用。

## 內容

| 檔案 | 內容 | 資料時效 |
|---|---|---|
| [`hsr_timetable.md`](./hsr_timetable.md) | 台灣高鐵 12 站票價表、車種、生效日、PDF 查詢指引 | 自 2026-02-02 起 |
| [`hsr_schedule.md`](./hsr_schedule.md) | 高鐵全車次時刻（南下＋北上，從 PDF 預先萃取的 Markdown 表格） | 自 2026-02-02 起 |
| [`HSR.pdf`](./HSR.pdf) | 台灣高鐵官方完整時刻表 PDF（北上+南下逐班車逐站時刻） | 自 2026-02-02 起 |
| [`airport_mrt_timetable.md`](./airport_mrt_timetable.md) | 桃園機場捷運 A1/A12/A13/A17/A18/A21/A22 雙向時刻表 | 至 2026-05-31 |

## 快速查詢

倉庫已附 `hsr-lookup` skill（`.claude/skills/hsr-lookup/`），Claude 在被詢問班次或機捷轉乘高鐵時會自動採用，直接讀取 `hsr_schedule.md` / `airport_mrt_timetable.md`，省去 PDF 解析時間。

PDF 改版時，執行 `python3 .claude/skills/hsr-lookup/scripts/extract_hsr_pdf.py` 重新生成 `hsr_schedule.md`。

## 資料來源
- 高鐵：台灣高速鐵路公司官方 PDF（2025-12-29 發行版）
- 機捷：桃園大眾捷運股份有限公司官網時刻表查詢（截圖日期 2026-04-28）

## 注意
- 時刻表會異動，**實際出行前請以官網最新公告為準**
- 高鐵：https://www.thsrc.com.tw/
- 機捷：https://www.tymetro.com.tw/

## 用途
此 repo 連接 claude.ai，方便在 web 端詢問特定班次、票價、轉乘等問題。
