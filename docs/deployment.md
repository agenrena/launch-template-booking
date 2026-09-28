# 部署

## 獨立 Compose

見 README 的 setup / compose / create_owner。所有資料庫與 backend/MCP 埠都在 Compose 私有網路，只有 web 對外；預設綁定 127.0.0.1:8080，Business Core 使用 8082，Runtime 後台使用 5188。

正式環境設定專用網域、HTTPS、ALLOWED_HOSTS、CSRF_TRUSTED_ORIGINS、COOKIE_SECURE=true。使用能覆寫 X-Forwarded-Proto 的可信反向代理；不要將私有 backend 直接公開。持久化 PostgreSQL 並安排備份；此模板不自行實作 Runtime 的備份／復原管理。

## Agenrena Runtime

runtime.json 宣告 Django + static frontend + optional MCP，以及 django_admin bootstrap。Runtime 注入 DATABASE_URL、SECRET_KEY、Host/CSRF/SSL 設定。後端 8000、前端 8080、MCP 8765，GET /health/ 驗證 DB。

先 migrate，再 runtime_bootstrap，再啟動服務。Bootstrap 使用 BOOTSTRAP_ADMIN_USERNAME / BOOTSTRAP_ADMIN_PASSWORD，只建立第一位有效 owner，不重設既有帳號。

MCP API URL 優先使用 BOOKING_API_URL，亦接受核心副本的 CORE_API_URL。現有 Runtime provider 注入 BOOKING_API_URL 即可。

## Agenrena Vendor 憑證

每個部署出去的 App 是一個 Agenrena Vendor，需要自己的 `AGENRENA_VENDOR_ID` 與 `AGENRENA_VENDOR_SECRET`（`bvs_…`）。目前由 Agenrena admin 為這個 App 建立 Vendor 並發出 secret，部署者把兩個值放進部署環境（Compose 的 `.env` 或 Runtime 的秘密設定）；`AGENRENA_BASE_URL` 預設 `https://api.agenrena.com`。沒有設定時 Agenrena 功能關閉，其他功能照常。

secret 只放在部署環境：不進原始碼、Git、打包 ZIP、log、API 回應或前端。商家的 Coding Agent 讀得到部署環境；這把 secret 只能代表這個 App，拿到也只能對已授權這個 App 的店發訊息，不會越權到其他商家。

輪替（手動）：Agenrena 為同一個 Vendor 發一把新 secret（新舊可同時有效）→ 更新部署環境並重啟 backend → 確認通知正常 → 在 Agenrena 停用舊的。App 以 secret 區分 token 快取，換新 secret 後會自動換新 token。懷疑外洩時立即停用舊 secret；目前平台上已換出的 token 最長仍可用 1 小時。

App 只連出到 `AGENRENA_BASE_URL`；Agenrena 不回呼 App，不需要對外開放額外端點。

使用 Runtime 的 scripts/pack.py 或相等的排除規則打包。不含 .env、node_modules、.venv、Git、.runtime、資料庫或顧客資料。ZIP root 為此專案根目錄。

本次重寫 saas_template/booking。Runtime 內 templates/booking 仍是舊副本，尚未同步；現有後台下載不會自動使用此版本。未對 AWS 執行部署或建立資源。

本版只供全新資料庫。重寫的 initial migration 不可用來升級舊 Booking schema。
