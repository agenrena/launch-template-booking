# 客製開發

這是完整獨立副本，不 import ../business_core。核心在 backend/core、業務在 backend/booking；商家都可直接修改。

## 本機

Python 3.13、Node 22.12+、PostgreSQL 14+。使用自己的虛擬環境，pip install -r backend/requirements.txt。設定 SECRET_KEY、DATABASE_URL、COOKIE_SECURE=false、CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173。後端不自動讀取 .env，Compose 會讀取根目錄 .env。

```sh
.venv/bin/python backend/manage.py migrate
.venv/bin/python backend/manage.py create_owner --username owner
.venv/bin/python backend/manage.py runserver 127.0.0.1:8040
npm ci --prefix frontend
npm run dev --prefix frontend
```

Vite 5173 代理 API 8040、MCP 8765。BOOKING_DEV_API / BOOKING_DEV_MCP 可調整。MCP 設 BOOKING_API_URL=http://127.0.0.1:8040/api/agent-api/ 再 npm start --prefix mcp。

## 客製入口

- 人的授權：core/permissions.py，owner/admin。Agent 角色：AgentRole / AgentPermission，透過新的 migration 調整，不另做一套工具內權限判斷。
- 登入／成員／金鑰：core/services.py、core/views.py 與核心前端頁面。
- 服務、排班、顧客、預約：booking/models.py、serializers.py、services.py、views.py。
- 空檔：booking/availability.py；改時長／緩衝／資源規則要同時調整 create/reschedule 和資料庫防撞單約束。
- 顧客 scope：booking/services.customer_rows 同時檢查 permission 與 identity，物件 ID 查詢也必須經過它。
- 姓名僅存 core.CustomerIdentity.display_name，電話屬 Booking.Customer。顧客 reference 僅存 core.CustomerIdentity.agenrena_customer_ref，不以姓名合併。
- 顧客通知：booking/notifications.py 決定建立／改期／取消的卡片內容，經 core.services.notify_customer 在交易提交後送到顧客與那間店的 Agenrena 對話。新增事件時沿用 announce，message_id 對同一事實保持穩定；測試以 patch("core.agenrena._request", …) 模擬平台。
- 一套 App 就是一間店：人員、預約、空檔都沒有據點欄位。連鎖店每間店各自部署。
- UI：frontend/src/booking；共同頁面在 frontend/src/pages。登入先載入基本殼層，日曆另行載入。
- MCP：core.ts 的共通工具與 server.ts 的預約工具合成一個 server。HTTP 每次驗證 key；後端是授權的最終判定。

## 保留規則

UTC 儲存、店家時區顯示、輸入必須帶 offset。DST 處理按實際分鐘計算。Booking 保存價格／幣別與起訖時間快照；改期不因目錄更新而改時長。相同有效預約重試回原筆；取消後重訂是新筆。

新的 PostgreSQL schema 含 btree_gist extension，建立 extension 需要資料庫管理權限；Runtime 的 migration role 必須已具備適當支援。正常 App 不應取得 schema 管理權限。

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
