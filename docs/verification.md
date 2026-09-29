# 驗證紀錄

## 2026-09-30：預設在這台電腦上執行，樣式集中於 theme.css

同步 business_core 的本機執行與樣式重構，並拿掉兩條 PostgreSQL exclusion constraint。Agenrena 未設定，沒有連到真實平台。

| 檢查 | 結果 |
|---|---|
| Django | 65 項測試在 SQLite 與 PostgreSQL 17 都通過，含「兩位顧客同時訂同一人員同一時段只成立一筆」「同時重試只一筆」的並行測試（拿掉資料庫限制後，由 services 的鎖與 SQLite IMMEDIATE 保證）；makemigrations --check 通過 |
| 首次啟動 | 乾淨副本、只有 `/usr/bin:/bin` 的 PATH 執行 `./start.command --no-browser`：安裝、建置、建立 `data/db.sqlite3`，在 127.0.0.1:8080 提供畫面 |
| 首次建立擁有者 | 真實 HTTP：可建立 → 直接登入 → 第二次 403 |
| 示範資料 | `./start.command manage seed_demo` 建立服務、兩位人員與工作時間 |
| 本機 Agent（stdio） | 用後台給的設定（名稱 `booking`）：9 個工具；get_shop → find_availability → create_booking 成立；重試回同一筆；另一位顧客訂同一人員同一時段回 `slot_unavailable`，替代時段是另一位人員 |
| 畫面 | Chrome 截圖：預約日曆亮色／暗色、總覽（新增「服務與排班」步驟，有服務、人員與工作時間時顯示「可預約」）、服務與排班（暗色）、手機寬度。依截圖補上 `.panel + .section-head` 間距 |
| 換品牌 | 測試副本只改 `theme.css` 的 `--brand` 成藍色，重新執行自動重建，側欄、按鈕、日曆按鈕、今天欄位與預約事件全部變藍 |
| Docker Compose | 乾淨副本 `docker compose up --build`：PostgreSQL 不需要 btree_gist 即可 migrate；backend 由 waitress 服務；經 nginx 的畫面、health、runtime_bootstrap、seed_demo、登入、網頁建立擁有者 403、HTTPS proxy 後 MCP 網址為 `https://`、HTTP MCP 核心工具，以及預約建立／重試同一筆／另一位顧客同時段 `slot_unavailable`。測完 `down -v` 刪除 |
| Frontend / MCP | 正式建置通過（check:style：沒有 theme.css 以外的色碼）；MCP 10 項測試通過 |
| 程式整理 | Ruff、Prettier（修改過的檔案） |

尚未執行：Windows 上的 `start.bat`、`scripts/http_smoke.py`（PostgreSQL 開發路線，其中的預約 smoke 需要它提供的 `SMOKE_BOOKING`）、與真實 Agenrena 的授權與通知。

後續修正：預約日曆原本高度為自動、沒有內部捲動區，`scrollTime="08:00:00"` 不生效，打開時從 0 點開始。改為固定 `height="75vh"` 後，桌面與手機截圖確認打開時從 8 點開始、9:00 的預約直接可見，往下仍可捲到 23 點。

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
