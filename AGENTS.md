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
- Keep PostgreSQL exclusion constraints for staff AND customer overlap.
- Keep idempotent creates/cancels, atomic rescheduling, explicit-offset timestamps, DST handling, and original duration/price/currency on reschedule.
- Audit successful mutations and Agent queries; do not log credentials, Vendor secrets, consent links, profile values, notes or message text.
- Booking created/rescheduled/cancelled (by Agent or staff) calls booking.notifications.announce, which uses core notify_customer after commit. Cards carry service, person, time and price, never notes; delivery never fails or rolls back a booking. Tests fake core.agenrena._request.
- Fresh-install schema only: user authorized rewriting initial migrations, no old database migration path.
- Do not modify sibling business_core or Runtime's templates/booking as part of this source template work.
- Validate with PostgreSQL tests core.tests + booking.tests, frontend build, MCP tests, and scripts/http_smoke.py for integration changes.
- No .env, credentials, production/customer data, virtualenvs or node_modules in deliveries.
