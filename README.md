# Agenrena Booking

一份完整、可獨立客製的預約 App，一間店一套。它由 **Business Core 的副本 + Booking 業務** 組成，和 `business_core` 同層，但執行時不依賴它。

這間店在 Agenrena 上是一個 Business Profile，這套 App 是它的軟體。商家以後台管理，商家自己帶來的 Agent 透過 MCP 面對顧客；Coding Agent 負責修改程式。預設就跑在店家自己的電腦上，需要時再放到伺服器。連鎖店每間店各自一套。

## 能力與資料歸屬

| 能力 | 設計 |
|---|---|
| 核心 | 這間店（名稱、介紹、地址、電話、時區）、獨立登入、owner/admin、團隊、Agent 金鑰／權限表、操作紀錄 |
| 服務 | 服務項目、固定時長與價格 |
| 人員 | 每人設定每週工作時間與不可預約時段 |
| 顧客 | 電話留在 Booking；姓名與 Agenrena reference 由核心身分管理 |
| 預約 | 保存人員、顧客、時段、歷史報價與幣別；改期保留原時長／報價／幣別 |
| MCP | 3 個核心工具 + 6 個預約工具，預設同一顧客服務權限組 |
| Agenrena | App 是這間店的 Vendor；店家授權一次後，預約建立、改期、取消會以卡片送進顧客與這間店的對話 |

同一位人員或同一位顧客不能有重疊的預約。服務人員不等於後台帳號，owner/admin 都可以管理這間店的營運。

這是全新資料庫的 schema，使用者已確認沒有舊資料要搬移。**不要對舊版 Booking 資料庫直接套用這組重寫的初始 migration。**

## 在這台電腦上開始（預設）

一間店 = 一個資料夾。不需要 Docker 或資料庫伺服器，只需要 [uv](https://docs.astral.sh/uv/) 與 Node.js 22.12+；沒有的話請 Agent 安裝。

- macOS：點兩下 `start.command`（或在終端機執行 `./start.command`）
- Windows：點兩下 `start.bat`

第一次會自動產生這台電腦專用的 `.env`、安裝套件、建置畫面並建立資料庫，完成後打開 **http://127.0.0.1:8080**，在畫面上建立擁有者帳號（只能在這台電腦上建立，且只有第一次）。之後再執行只會直接開啟；程式被 Agent 改過時會自動重新建置。按 Ctrl+C 或關掉視窗就停止。

依序填商家資料 → 新增服務 → 新增人員／工作時間 → 建立預約。第一次見店家時可以先放入示範服務與排班：

```sh
./start.command manage seed_demo        # Windows：start.bat manage seed_demo
```

不會建立示範帳密、金鑰或顧客；重跑不覆蓋既有設定。首次資料庫只有 Business、預約設定和顧客服務權限組，沒有帳號、服務、人員、顧客或預約。

**資料都在 `data/`**（SQLite）。備份或換電腦：停止 App 後複製整個專案資料夾（含 `data/` 與 `.env`）。`data/` 與 `.env` 不進 Git。登入使用獨立 Django session，不接 Agenrena SSO，也不共用 Firebase。密碼可在「我的帳號」更改；忘記時執行 `./start.command manage changepassword <帳號>`，或請 Agent 代為執行。

要隨時從外面連線時，改用 Docker Compose + PostgreSQL 放到伺服器上，見 [部署](docs/deployment.md)。同一份程式碼，以 `DATABASE_URL` 決定用哪種資料庫。

## 顧客服務 Agent

這間店的 Agent 由商家自己帶來、跑在商家這一端。擁有者在「Agent 連接」建立金鑰（只顯示一次）：

- **Agent 在這台電腦上（預設）**：頁面直接給一段 `mcpServers` 設定（`node mcp/dist/index.js --stdio`，金鑰已填好），交給 Agent 即可，不需要對外開放任何網址。
- **App 放在伺服器上**：連到 `https://<網域>/mcp` 並帶 `Authorization: Bearer abc_…`。

金鑰不能放在顧客端。

Agenrena 代理聊天室附帶這間店的 `customer_ref`（`bcr_` 加 32 個 hex）；工具接收它，核心對應至 `CustomerIdentity.agenrena_customer_ref`。App 內的 Booking Customer 以一對一關係連結該 identity，不另存第二份 reference。姓名不自動合併。

第一版信任授權 Agent 正確帶入對話 reference，不加簽章。持有商家金鑰的 Agent 可以提交其他 reference，這個欄位本身不是身分憑證。

顧客確認服務、人員、時間及價格後才建立預約；改期直接修改原筆，不先取消再訂。

擁有者在「商家資料」連接 Agenrena（部署需注入 `AGENRENA_VENDOR_ID`／`AGENRENA_VENDOR_SECRET`，見 [部署](docs/deployment.md)）。連接後，不論 Agent 或後台人員建立、改期、取消預約，顧客都會在與這間店的 Agenrena 對話收到一張預約卡片（服務、人員、時間、金額；不含備註）。沒有 reference 的顧客或尚未連接時不發送；發送失敗不影響預約。

## 明確的簡化

- 所有人員都能提供共用服務；一位人員一次一位顧客。
- 15 分鐘起始時間間隔；工作時間不跨午夜，午休用兩段排班。
- 停用人員／服務、調整排班不自動取消預約；後台仍可查歷史與取消未來預約。
- 一套 App 只服務一間店；連鎖店的共用菜單或合併報表不在範圍內。
- 通知只在預約建立、改期、取消時送出；沒有提醒排程。
- 沒有付款、候補、會員點數、到店／完成狀態或公開自助預約網頁。

## 程式結構

```text
scripts/start.py               在這台電腦上執行（start.command / start.bat 呼叫它）
frontend/src/theme.css         顏色、字體、圓角與暗色模式（換品牌只改這裡，預約日曆也跟著變）
backend/core/                  共同能力的本地副本（含 Agenrena 連接與 notify_customer）
backend/booking/models.py      Booking domain、Customer.identity
backend/booking/services.py    預約寫入／授權／操作紀錄
backend/booking/availability.py 空檔與時區規則
backend/booking/notifications.py 預約卡片（建立／改期／取消）
frontend/src/pages/            核心後台頁面
frontend/src/booking/          日曆、顧客、服務與排班
mcp/src/core.ts                核心顧客服務工具
mcp/src/server.ts              預約工具，組合核心工具
```

我們維護官方模板的副本；已交給商家的版本不自動合併共同基礎更新。文件中的「副本」表示原始碼可直接改寫，不是執行期共用 package。

## 驗證

```sh
# 沒有 DATABASE_URL 時用 SQLite；兩種資料庫都要通過
.venv/bin/python backend/manage.py test core.tests booking.tests --noinput
DATABASE_URL=postgresql://… .venv/bin/python backend/manage.py test core.tests booking.tests --noinput
.venv/bin/python backend/manage.py makemigrations --check --dry-run
npm run build --prefix frontend
npm test --prefix mcp
./start.command --no-browser   # 實際啟動本機版
# 伺服器路線：下列腳本自行建立及刪除獨立 PostgreSQL smoke database，需開發用 CREATEDB 權限
.venv/bin/python scripts/http_smoke.py
```

## 授權

[MIT](LICENSE)。可以免費使用、修改，也可以拿去幫店家建置並收費，不需要向 Agenrena 分潤或回報；只要保留 LICENSE 檔即可。「Agenrena」名稱與商標不在授權範圍內，改過的版本請不要宣稱是 Agenrena 官方版本。

[產品決策](docs/product-decisions.md) · [客製開發](docs/development.md) · [Agent 契約](docs/agent.md) · [部署](docs/deployment.md) · [驗證紀錄](docs/verification.md)

## 軟體名稱（2026-10-02）

登入頁、後台左上角和瀏覽器分頁使用商家的軟體名稱；直接從 GitHub 取得時預設為 `Booking`。Agenrena Business 下載會寫入 `backend/app-config.json` 的 `software_name`（最多 120 字），首次建立商家資料時保存至資料庫。檔案缺少、空白或無效時使用模板預設值。後台「商家資料」可改名，之後啟動不會用下載設定覆蓋。軟體名稱與商家名稱分開，也不會同步改動 Agenrena 上的 App/Vendor 名稱。頁底的 `Powered by Agenrena` 可自行移除，不影響功能。此版本只針對全新初始化，沒有舊資料搬移流程。
