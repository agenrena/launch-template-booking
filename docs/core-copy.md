# Business Core 副本關係

來源：同層 business_core，2026-09-30 版本（一間店一套 App、Agenrena 連接、樣式集中於 theme.css、預設在這台電腦上執行）。本專案是完整副本，沒有執行期跨資料夾 import、symlink 或共用套件依賴。

共同資料模型與登入／成員／金鑰／稽核服務保留在 backend/core。Booking 的明確延伸點：

- core/permissions.py 在既有 owner/admin 權限上增加營運操作。
- booking/migrations/0002_booking_permissions.py 將預約工具權限加到同一個 customer_service role。
- booking.Customer.identity 一對一連結核心 identity，不複製 reference 或顧客姓名。
- frontend/src/App.tsx 增加預約／顧客／服務排班導覽，業務頁面放在 frontend/src/booking。
- mcp/src/core.ts 保留共同工具，server.ts 再註冊 Booking 工具；API wrapper 使用繼承共用傳輸。
- core 測試的預設權限清單隨此模板新增能力調整，其餘核心測試（含 test_agenrena）沿用。
- booking/notifications.py 以核心 notify_customer 送出預約卡片。
- 前端 pages/Business、Agents、Agenrena、Account、Members、theme.css、ui.tsx 與核心相同；Audit、Overview（多「服務與排班」步驟）、api.ts、App.tsx（預約導覽與頁面）、icons.tsx（預約導覽圖示）、style.css（檔尾「預約」段落）在核心之上保留預約項目。
- config/settings.py 多 booking app 與 `MCP_NAME = "booking"`；config/urls.py 在核心路由後加入 booking.urls，前端的 catch-all 放在最後。
- scripts/start.py、start.command、start.bat、core/views.py 與核心相同。

維護官方模板時，先比較上游核心變更，再把適用修正整合到這些副本；不得直接覆蓋商家自己的客製版本。
