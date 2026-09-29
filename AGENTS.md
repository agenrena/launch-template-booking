# Agenrena Booking template

Read README.md and docs/product-decisions.md before changing scope.
This is a complete editable COPY of Business Core plus a booking domain for one store.
Do not import the sibling business_core at runtime or automatically sync its updates.

- One store per App/database: Business is the store. There is no Location/branch model; a chain deploys one App per store. Do not reintroduce branches unless requested.
- The store is one Agenrena Business Profile (a direction, not enforced on Agenrena). The App is its Agenrena Vendor; Vendor credentials come only from env (AGENRENA_VENDOR_ID/SECRET) and are never committed, logged, returned or given to the frontend/MCP. At most one grant (AgenrenaConnection singleton).
- Shared core lives in backend/core, common frontend pages, and mcp/src/core.ts.
- Booking rules live in backend/booking/services.py and availability.py. Console and MCP share them.
- Human roles are owner/admin; both can manage this store's bookings. Membership/keys/Agenrena connection remain owner-only.
- Agent roles are separate database tables. Default customer_service includes only customer-facing tools.
- Every Agent booking read/write must check its operation permission AND customer identity scope. Never look up a customer booking by ID alone.
- Customer.identity links to core.CustomerIdentity. The canonical name is identity.display_name. Reference is optional, unique agenrena_customer_ref in Agenrena's bcr_ + 32 hex format. Never merge by name/phone.
- Trust the authorized Agent to forward the Agenrena conversation reference; this is deliberately not signed identity verification.
- No staff/customer overlap: create/reschedule lock the customer identity and staff (select_for_update) inside transaction.atomic, then check, then write. PostgreSQL serializes on those locks; SQLite on its IMMEDIATE write transaction. There is no database-level overlap constraint, so booking writes go through booking/services.py.
- Keep idempotent creates/cancels, atomic rescheduling, explicit-offset timestamps, DST handling, and original duration/price/currency on reschedule.
- Audit successful mutations and Agent queries; do not log credentials, Vendor secrets, consent links, profile values, notes or message text.
- Booking created/rescheduled/cancelled (by Agent or staff) calls booking.notifications.announce, which uses core notify_customer after commit. Cards carry service, person, time and price, never notes; delivery never fails or rolls back a booking. Tests fake core.agenrena._request.
- Fresh-install schema only: user authorized rewriting initial migrations, no old database migration path.
- Do not modify sibling business_core or Runtime's templates/booking as part of this source template work.
- Local is the default: scripts/start.py (start.command / start.bat) runs everything on this computer with SQLite in data/, no Docker, no database server. DATABASE_URL switches to PostgreSQL for hosting (Compose/Runtime). Keep both working; use only features both databases support (no django.contrib.postgres). waitress serves both.
- LOCAL_APP (set by start.py) opens first-owner setup in the browser only from loopback and only while no active owner exists, and makes the console show the stdio MCP config. Hosted installs never set it.
- The store's Agent is brought by the merchant and runs on their side; locally it launches the MCP over stdio. Agenrena never calls into the App.
- Styling: every colour, font, radius and density value lives in frontend/src/theme.css. To rebrand, change --brand (and --brand-fg if button text is unreadable); hovers, soft backgrounds and the FullCalendar colours are derived from it. style.css and components use only var(--…); `npm run check:style` (also part of build) rejects colour literals elsewhere. Status colours (--ok, --danger) stay independent of the brand. Dark mode follows the system via the media block in theme.css.
- Validate backend changes with core.tests + booking.tests on SQLite and PostgreSQL, frontend build, MCP tests, ./start.command --no-browser for startup changes, and scripts/http_smoke.py (PostgreSQL) for hosted integration changes.
- No .env, credentials, production/customer data, virtualenvs or node_modules in deliveries.
