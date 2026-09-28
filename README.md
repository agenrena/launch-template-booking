# Agenrena Booking

一份完整、可獨立客製的預約 App，一間店一套。它由 **Business Core 的副本 + Booking 業務** 組成，和 `business_core` 同層，但執行時不依賴它。

這間店在 Agenrena 上是一個 Business Profile，這套 App 是它的軟體。商家以後台管理，Business Agent 透過 MCP 面對顧客；Coding Agent 負責修改程式與提交 Runtime 部署。連鎖店每間店各自部署一套。

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

## 啟動

需要 Docker Compose 與 Python 3。原始碼開發使用 Python 3.13、Node 22.12+、PostgreSQL 14+。

```sh
python3 scripts/setup.py
docker compose up --build -d
docker compose exec backend python manage.py create_owner --username owner
```

第三步私下設定第一位擁有者的密碼。開啟 **http://localhost:8080**。

依序填商家資料 → 新增服務 → 新增人員／工作時間 → 建立預約。可選擇加入示範服務與排班：

```sh
docker compose exec backend python manage.py seed_demo
```

不會建立示範帳密、金鑰或顧客；重跑不覆蓋既有設定。`setup.py` 拒絕覆蓋 `.env`。首次資料庫只有 Business、預約設定和顧客服務權限組，沒有帳號、服務、人員、顧客或預約。

登入使用獨立 Django session，不接 Agenrena SSO，也不共用 Firebase。密碼可在「我的帳號」更改；忘記時由部署管理者執行 `docker compose exec backend python manage.py changepassword <username>`。

## 顧客服務 Agent

這間店在 Agenrena 上的客服 Agent 使用擁有者在「Agent 連接」建立的金鑰，連到 `/mcp` 並帶 `Authorization: Bearer abc_…`。正式公開使用 HTTPS，金鑰不能放在顧客端。

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
# 已設定專用測試 PostgreSQL 的 DATABASE_URL / SECRET_KEY
.venv/bin/python backend/manage.py test core.tests booking.tests --noinput
.venv/bin/python backend/manage.py makemigrations --check --dry-run
npm run build --prefix frontend
npm test --prefix mcp
# 下列腳本自行建立及刪除獨立 smoke database，需開發用 CREATEDB 權限
.venv/bin/python scripts/http_smoke.py
```

[產品決策](docs/product-decisions.md) · [客製開發](docs/development.md) · [Agent 契約](docs/agent.md) · [部署](docs/deployment.md) · [驗證紀錄](docs/verification.md)
