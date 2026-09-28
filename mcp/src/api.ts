export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(`API returned ${status}`);
  }
}
export class CoreApi {
  private base: string;
  constructor(
    base: string,
    private key: string,
  ) {
    this.base = base.endsWith("/") ? base : base + "/";
  }
  session() {
    return this.call("session/");
  }
  business() {
    return this.call("business/");
  }
  profile(args: { customer_ref: string }) {
    return this.call(
      `customer-profile/?customer_ref=${encodeURIComponent(args.customer_ref)}`,
    );
  }
  updateProfile(args: { customer_ref: string; display_name: string }) {
    return this.call("customer-profile/", args);
  }
  protected async call(
    path: string,
    body?: unknown,
    method?: string,
  ): Promise<unknown> {
    const response = await fetch(new URL(path, this.base), {
      method: method ?? (body === undefined ? "GET" : "POST"),
      signal: AbortSignal.timeout(15000),
      headers: {
        Authorization: `Bearer ${this.key}`,
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) throw new ApiError(response.status, payload);
    return payload;
  }
}

export class BookingApi extends CoreApi {
  shop() {
    return this.call("shop/");
  }
  availability(args: Record<string, unknown>) {
    return this.query("availability/", args);
  }
  bookings(args: Record<string, unknown>) {
    return this.query("bookings/", args);
  }
  createBooking(args: Record<string, unknown>) {
    return this.call("bookings/", args);
  }
  changeBooking(id: string, args: Record<string, unknown>) {
    return this.mutate(`bookings/${id}/`, args, "PATCH");
  }
  cancel(id: string, args: Record<string, unknown>) {
    return this.call(`bookings/${id}/cancel/`, args);
  }
  private query(path: string, args: Record<string, unknown>) {
    const search = new URLSearchParams();
    for (const [k, v] of Object.entries(args))
      if (v !== undefined) search.set(k, String(v));
    return this.call(path + "?" + search);
  }
  private mutate(path: string, args: Record<string, unknown>, method: string) {
    return this.call(path, args, method);
  }
}
