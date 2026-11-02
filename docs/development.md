# 客製開發

這是完整獨立副本，不 import ../business_core。核心在 backend/core、業務在 backend/booking；商家都可直接修改。

## 本機

Python 3.13、Node 22.12+。沒有 `DATABASE_URL` 時用 SQLite（`data/`，或 `DATA_DIR` 指定的資料夾）；設定後用 PostgreSQL 14+。兩種都是正式支援的路線，後端測試兩種都要過。

最直接的方式是 `./start.command`：它就是商家實際執行的樣子，改完程式重新執行會自動重建；`./start.command manage <指令>` 以這台電腦的設定執行 Django 管理指令。需要前端即時重載時，使用自己的虛擬環境，pip install -r backend/requirements.txt，設定 SECRET_KEY、COOKIE_SECURE=false、CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173。後端不自動讀取 .env（start.py 與 Compose 會）。

```sh
.venv/bin/python backend/manage.py migrate
.venv/bin/python backend/manage.py create_owner --username owner
.venv/bin/python backend/manage.py runserver 127.0.0.1:8040
npm ci --prefix frontend
npm run dev --prefix frontend
```

Vite 5173 代理 API 8040、MCP 8765。BOOKING_DEV_API / BOOKING_DEV_MCP 可調整。MCP 設 BOOKING_API_URL=http://127.0.0.1:8040/api/agent-api/ 再 npm start --prefix mcp。

Agent 客戶端的連線設定見 [MCP 連線 JSON 範例](agent.md#mcp-連線-json-範例)。

## 使用 Agenrena 聊天入口

Core 在授權完成或手動檢查既有授權後，將 Agenrena 回傳的商家公開聊天網址存入 `AgenrenaConnection.chat_url`。管理端可從 `GET /api/console/agenrena/` 的 `chat_url` 取得；未連接或沒有網址時為 `null`，此時不要產生聊天連結。這是需要管理端登入的 API，顧客介面如何取得公開聊天網址由 fork 專案決定。

網址形式例如 `https://agenrena.com/s/i/<business_short_id>/chat`。請使用回傳的完整 `chat_url`，不要自行拼接網域、路徑或商家 ID。不需要預填訊息時直接使用原網址；需要時加上 `text` query parameter：

```js
function buildChatLink(chatUrl, message = "") {
  if (!chatUrl) return null;
  if (!message) return chatUrl;
  const url = new URL(chatUrl);
  url.searchParams.set("text", message);
  return url.toString();
}

const chatLink = buildChatLink(
  connection.chat_url,
  "請加入我的專案，邀請碼是 ABC-123",
);
```

`text` 傳完整原始訊息，包含中文、空白或換行皆可；`URLSearchParams` 會處理 URL 編碼，不要先呼叫 `encodeURIComponent`。產生的連結只用於該次入口，不要覆寫保存的基礎 `chat_url`。

開啟連結會進入商家對話（需要時先登入），`text` 只會預填到可編輯的輸入框，仍由使用者手動送出；點擊連結不會自動傳訊或執行業務操作。按鈕、QR code、預填內容及收到訊息後的業務處理由 fork 專案實作。

## 客製入口

- 人的授權：core/permissions.py，owner/admin。Agent 角色：AgentRole / AgentPermission，透過新的 migration 調整，不另做一套工具內權限判斷。
- 登入／成員／金鑰：core/services.py、core/views.py 與核心前端頁面。
- 服務、排班、顧客、預約：booking/models.py、serializers.py、services.py、views.py。
- 空檔：booking/availability.py；改時長／緩衝／資源規則要同時調整 create/reschedule 的重疊檢查。
- 不重疊：create/reschedule 在 `transaction.atomic` 裡先鎖顧客 identity 與人員（`select_for_update`），再檢查、再寫入。PostgreSQL 靠這些鎖排隊，SQLite 靠寫入交易的 IMMEDIATE 模式排隊；沒有資料庫層的防撞單約束，所以預約的寫入都要經過 services。只用兩種資料庫都有的功能（不要用 `django.contrib.postgres`）。
- 顧客 scope：booking/services.customer_rows 同時檢查 permission 與 identity，物件 ID 查詢也必須經過它。
- 姓名僅存 core.CustomerIdentity.display_name，電話屬 Booking.Customer。顧客 reference 僅存 core.CustomerIdentity.agenrena_customer_ref，不以姓名合併。
- 顧客通知：booking/notifications.py 決定建立／改期／取消的卡片內容，經 core.services.notify_customer 在交易提交後送到顧客與那間店的 Agenrena 對話。新增事件時沿用 announce，message_id 對同一事實保持穩定；測試以 patch("core.agenrena._request", …) 模擬平台。
- 一套 App 就是一間店：人員、預約、空檔都沒有據點欄位。連鎖店每間店各自部署。
- UI：frontend/src/booking；共同頁面在 frontend/src/pages。登入先載入基本殼層，日曆另行載入。
- 更換外觀：只改 `frontend/src/theme.css`。換品牌色改 `--brand`（淺色品牌色時把 `--brand-fg` 改成深色），淺底、hover、日曆按鈕與事件顏色會自動跟著變；暗色模式在同檔的 `prefers-color-scheme` 區塊。`style.css` 與元件只能用 `var(--…)`，`npm run check:style`（build 也會跑）會擋下寫死的顏色。預約專用樣式在 style.css 的「預約」段落，FullCalendar 的 `--fc-*` 變數也在那裡接到 theme。
- MCP：core.ts 的共通工具與 server.ts 的預約工具合成一個 server。HTTP 每次驗證 key；後端是授權的最終判定。

## 保留規則

UTC 儲存、店家時區顯示、輸入必須帶 offset。DST 處理按實際分鐘計算。Booking 保存價格／幣別與起訖時間快照；改期不因目錄更新而改時長。相同有效預約重試回原筆；取消後重訂是新筆。


## 驗證

```sh
.venv/bin/python backend/manage.py test core.tests booking.tests --noinput
.venv/bin/python backend/manage.py makemigrations --check --dry-run
npm run build --prefix frontend
npm test --prefix mcp
```

scripts/http_smoke.py 在提供的**開發用** PostgreSQL 上建立隨機命名的獨立 database，啟動短暫 API、Vite 與 MCP，驗證真實預約流程。結束會清除自建 database／程序。需 CREATEDB 權限、npm ci 及 MCP build。它不改既有 App 資料。

## 客製：共用設備與店員角色

模板只附 Django 帳號密碼與 owner/admin。櫃檯平板、店員權限或 Firebase 登入屬於各店自己的管理方式，由商家的 Coding Agent 依需求實作。常見做法與要守的規則：

- **店員角色**：在 `core/permissions.py` 的 `HUMAN_PERMISSIONS` 新增角色並列出權限，同時更新 `Membership` 的 choices 與 constraint（新增 migration）。業務規則只看權限，不必改。
- **共用設備（例如櫃檯平板用配對碼登入）**：新增一個 authentication class 與 `Actor` 種類（例如 `device`），在 `authorize` 為它給固定、較小的權限。
  - 設備憑證只存雜湊，放在 HttpOnly、SameSite=Strict、正式環境 Secure 的 cookie；寫入 cookie 的請求要驗 CSRF。
  - 每次請求重新檢查是否過期或停用，停用下一次請求就生效；每台設備可個別停用。
  - 配對碼要短時效、單次使用，並限制頻率；只知道畫面上的配對碼不能領走憑證（領取時要搭配發起配對的瀏覽器本身的憑證）。
  - 設備的操作寫入操作紀錄時記錄「哪台設備」，不要冒用授權它的人的身分。
- **Firebase 等外部登入**：替換 session/login/logout 與前端登入頁，保留 Membership 授權、CSRF 與操作紀錄。
