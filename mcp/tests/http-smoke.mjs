import assert from "node:assert/strict";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
const { SMOKE_MCP_URL, SMOKE_AGENT_KEY } = process.env;
const client = new Client({ name: "business-core-smoke", version: "1" });
await client.connect(
  new StreamableHTTPClientTransport(new URL(SMOKE_MCP_URL), {
    requestInit: { headers: { Authorization: `Bearer ${SMOKE_AGENT_KEY}` } },
  }),
);
try {
  const { tools } = await client.listTools();
  assert.equal(tools.length, 9);
  const business = await client.callTool({
    name: "get_business",
    arguments: {},
  });
  assert.equal(business.isError, false);
  const customer_ref = "bcr_5e0ce0000000000000000000000000a1";
  const args = { customer_ref, display_name: "Smoke customer" };
  const first = await client.callTool({
    name: "update_customer_profile",
    arguments: args,
  });
  const second = await client.callTool({
    name: "update_customer_profile",
    arguments: args,
  });
  assert.deepEqual(
    JSON.parse(first.content[0].text),
    JSON.parse(second.content[0].text),
  );
  const other = await client.callTool({
    name: "get_customer_profile",
    arguments: { customer_ref: "bcr_5e0ce0000000000000000000000000b2" },
  });
  assert.equal(JSON.parse(other.content[0].text).profile, null);

  const config = JSON.parse(process.env.SMOKE_BOOKING);
  async function call(name, args) {
    const result = await client.callTool({ name, arguments: args });
    assert.equal(result.isError, false, JSON.stringify(result));
    return JSON.parse(result.content[0].text);
  }
  const shop = await call("get_shop", {});
  assert.ok(shop.staff.length >= 1);
  const available = await call("find_availability", {
    service: config.service,
    date_from: config.date,
  });
  const slot = available.slots[0];
  const input = {
    customer_ref,
    service: config.service,
    start: slot.start,
    staff_id: slot.staff[0].id,
  };
  const booking = await call("create_booking", input);
  const repeated = await call("create_booking", input);
  assert.equal(repeated.id, booking.id);
  const forbidden = await client.callTool({
    name: "cancel_booking",
    arguments: {
      booking_id: booking.id,
      customer_ref: "bcr_5e0ce0000000000000000000000000b2",
    },
  });
  assert.equal(forbidden.isError, true);
  const options = await call("find_availability", {
    service: config.service,
    date_from: config.date,
    booking_id: booking.id,
    customer_ref,
  });
  const replacement = options.slots.find((s) => s.start !== booking.start);
  const moved = await call("reschedule_booking", {
    booking_id: booking.id,
    customer_ref,
    staff_id: replacement.staff[0].id,
    start: replacement.start,
  });
  assert.equal(moved.start, replacement.start);
  assert.equal(moved.price, booking.price);
  assert.equal(moved.currency, booking.currency);
  assert.equal((await call("list_bookings", { customer_ref })).count, 1);
  const cancelled = await call("cancel_booking", {
    booking_id: booking.id,
    customer_ref,
  });
  assert.equal(cancelled.status, "cancelled");
  await call("cancel_booking", { booking_id: booking.id, customer_ref });
  console.log(
    "Booking HTTP: availability, scoped booking/retry, reschedule, cancellation passed.",
  );
  console.log(
    "Streamable HTTP: initialize, tools/list, scoped read/write and retry passed.",
  );
} finally {
  await client.close();
}
