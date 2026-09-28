# 驗證紀錄

## 2026-09-28：一間店一套 App，同步核心的 Agenrena 連接

在 scratchpad 的獨立 venv 與臨時 PostgreSQL 14 叢集執行，不讀寫商家、Agenrena 或 Runtime 的既有資料庫；Agenrena 以模擬的 HTTP 回應代替。當天先做過以據點為單位的版本，同日決定拿掉 Location；以下為最終版本的結果，initial migration 直接重寫（含 btree_gist extension）。

| 檢查 | 結果 |
|---|---|
| PostgreSQL 後端 | 62 項 core.tests + booking.tests 通過：核心 32 項（含 Agenrena 12 項）與預約 30 項。預約含空檔列出各人員、Agent 查空檔與預約、get_shop、停用人員不能新預約但保留歷史、重試保留報價快照、顧客與人員不能重疊（含資料庫排他約束與並行）、改派人員保留快照、改期撞期不部分寫入、休假／格線／過去時間、DST、顧客範圍與權限、首次顧客、稽核不含私人值、嚴格輸入；通知：建立／重試／改期／取消卡片、重試沿用 message_id、備註不送出、後台建立也通知、無 reference 不送、送達失敗不影響預約 |
| Migration | 全新 database migrate、makemigrations --check --dry-run、seed_demo 通過 |
| Frontend | TypeScript 與 Vite 正式編譯通過（Node 22.23.2） |
| MCP | 10 項測試通過（9 個工具），拒絕自編 reference |
| 真實 HTTP | `scripts/http_smoke.py`：後台登入、Agenrena 狀態（未設定）、get_shop、空檔／預約／重試、拒絕其他顧客 reference、改期、取消與重試、撤銷金鑰被拒絕通過 |
| Compose | 以假值執行 docker compose config --quiet 通過 |
| 靜態整理 | Ruff check / format 通過，TypeScript/CSS/MCP 使用 Prettier |

尚未驗證：瀏覽器畫面與 QR 連接流程、與真實 Agenrena 的授權與發訊息、完整 Docker image build／Compose 啟動、Runtime 部署。

## 2026-09-27：多據點重寫

2026-09-27。使用獨立暫存原始碼與 PostgreSQL 17；未讀寫任何商家、Agenrena 或 Runtime 的既有資料庫。

| 檢查 | 結果 |
|---|---|
| PostgreSQL 後端 | 47 項 core.tests + booking.tests 通過 |
| 權限／身分 | owner/admin、CSRF、金鑰撤銷、單一 Agent 權限組及即時權限變更、顧客 reference 範圍、核心／Booking 共用身分通過 |
| 多據點 | 單店自動帶入、多店要求選店、人員與據點匹配、跨店改期、停用據點、日曆篩選、移店歷史保存通過 |
| 預約一致性 | PostgreSQL 人員／顧客排他約束、並行搶位／重試、跨店顧客防撞單、時長／報價／幣別快照、DST、失敗回滾通過 |
| Migration | 全新 database 的 migrate 與 makemigrations --check --dry-run 通過 |
| Frontend | TypeScript 與 Vite 正式編譯通過；日曆工作空間分開載入（Node 22.23.2） |
| MCP | 10 項協定與 HTTP wrapper 測試通過；實際列出 4 核心 + 6 預約工具 |
| 真實 HTTP | Vite proxy、session／CSRF 登入、後台商家／據點／服務／人員／排班建立、操作紀錄與登出通過 |
| 真實 Streamable HTTP | 選店查空檔、建立／重試、拒絕其他顧客 reference、跨店改期、取消／重試、撤銷 key 被拒絕通過 |
| Compose | docker compose config --quiet 通過 |
| 靜態整理 | Ruff check / format 通過，TypeScript/CSS 使用 Prettier |

尚未驗證：瀏覽器視覺與互動操作、完整 Docker image build／Compose 啟動、Runtime 真實部署、AWS 與 Agenrena 真實聊天室串接。API 成功不代表畫面驗收；GitHub Actions 已更新檢查流程但未宣稱遠端 CI 已執行。

HTTP smoke 自動建立隨機 database 與隨機帳密，結束即停止程序並清除該 database。交付不含 .env、密碼、Agent key、顧客資料、node_modules、virtualenv 或建置產物。

本次使用者明確允許重寫 schema，不包含舊版 Booking 資料庫的升級／資料搬移路徑。
