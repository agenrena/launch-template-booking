import test from "node:test";
import assert from "node:assert/strict";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { createServer } from "../dist/server.js";
import { BookingApi, ApiError } from "../dist/api.js";
const id = "f38fe48e-0e01-4c5b-8918-21c7f3af9bac";
async function connect(api) {
  const server = createServer(api),
    client = new Client({ name: "test", version: "1" });
  const [a, b] = InMemoryTransport.createLinkedPair();
  await server.connect(a);
  await client.connect(b);
  return {
    client,
    close: async () => {
      await client.close();
      await server.close();
    },
  };
}
test("conversation reference passes through booking writes", async () => {
  let args;
  const s = await connect({
    createBooking: async (a) => {
      args = a;
      return { id };
    },
  });
  try {
    const input = {
      customer_ref: "bcr_0123456789abcdef0123456789abcdef",
      service: id,
      staff_id: id,
      start: "2031-01-01T10:00:00+08:00",
      customer_name: "Ada",
    };
    const result = await s.client.callTool({
      name: "create_booking",
      arguments: input,
    });
    assert.equal(result.isError, false);
    assert.deepEqual(args, input);
  } finally {
    await s.close();
  }
});
test("reschedule availability carries booking and scoped reference", async () => {
  let args;
  const s = await connect({
    availability: async (a) => {
      args = a;
      return { slots: [] };
    },
  });
  try {
    const input = {
      service: id,
      booking_id: id,
      customer_ref: "bcr_0123456789abcdef0123456789abcdef",
    };
    await s.client.callTool({ name: "find_availability", arguments: input });
    assert.deepEqual(args, input);
  } finally {
    await s.close();
  }
});
test("booking error stays a structured tool error", async () => {
  const body = { error: "slot_unavailable", alternatives: [] };
  const s = await connect({
    changeBooking: async () => {
      throw new ApiError(409, body);
    },
  });
  try {
    const result = await s.client.callTool({
      name: "reschedule_booking",
      arguments: {
        customer_ref: "bcr_0123456789abcdef0123456789abcdef",
        booking_id: id,
        staff_id: id,
      },
    });
    assert.equal(result.isError, true);
    assert.deepEqual(JSON.parse(result.content[0].text), body);
  } finally {
    await s.close();
  }
});
test("HTTP wrapper sends PATCH for reschedule", async () => {
  const original = globalThis.fetch;
  let seen;
  globalThis.fetch = async (url, init) => {
    seen = { url: String(url), init };
    return new Response("{}", { status: 200 });
  };
  try {
    await new BookingApi(
      "http://booking.test/api/agent-api",
      "abc_key",
    ).changeBooking(id, {
      staff_id: id,
      customer_ref: "bcr_0123456789abcdef0123456789abcdef",
    });
    assert.equal(seen.init.method, "PATCH");
    assert.equal(seen.url, `http://booking.test/api/agent-api/bookings/${id}/`);
    assert.equal(JSON.parse(seen.init.body).staff_id, id);
  } finally {
    globalThis.fetch = original;
  }
});
