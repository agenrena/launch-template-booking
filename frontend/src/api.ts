import { DateTime } from "luxon";
import { QueryClient, useQuery } from "@tanstack/react-query";
export const client = new QueryClient({
  defaultOptions: { queries: { retry: false, staleTime: 15000 } },
});
let csrf = "";
export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const response = await fetch(`/api/console/${path}`, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const body =
    response.status === 204 ? {} : await response.json().catch(() => ({}));
  if (body.csrf_token) csrf = body.csrf_token;
  if (!response.ok) {
    if (response.status === 403 || response.status === 401)
      void client.invalidateQueries({ queryKey: ["session/"] });
    throw new Error(
      bookingErrors[body.error] ??
        (body.details
          ? typeof body.details === "string"
            ? body.details
            : JSON.stringify(body.details)
          : `請求失敗 (${response.status})`),
    );
  }
  return body as T;
}
export function useData<T>(path: string) {
  return useQuery({ queryKey: [path], queryFn: () => api<T>(path) });
}
export async function change<T>(path: string, method: string, data?: unknown) {
  const result = await api<T>(path, method, data);
  await client.invalidateQueries();
  return result;
}
export interface User {
  id: number;
  username: string;
  name: string;
  role: "owner" | "admin";
  is_active: boolean;
  permissions: string[];
}
export interface Business {
  name: string;
  about: string;
  address: string;
  phone: string;
  timezone: string;
}
export interface Page<T> {
  results: T[];
  page: number;
  pages: number;
  count: number;
}
export interface AgentRole {
  code: string;
  label: string;
  permissions: { code: string; label: string; scope: string }[];
}
export interface AgentKey {
  id: string;
  label: string;
  role_id: string;
  prefix: string;
  revoked_at: string | null;
  created_at: string;
}
export interface AgenrenaState {
  configured: boolean;
  status: "none" | "pending" | "connected" | "revoked" | "expired";
  business_name?: string;
  connected_at?: string | null;
  expires_at?: string;
}
export interface Audit {
  id: string;
  created_at: string;
  actor_type: string;
  actor_label: string;
  action: string;
  target_type: string;
  target_id: string;
  customer_id: string | null;
  detail: { fields?: string[]; role?: string; error?: string };
}

export function iso(value: string, zone: string) {
  const date = DateTime.fromISO(value, { zone });
  if (!date.isValid || date.toFormat("yyyy-MM-dd'T'HH:mm") !== value)
    throw new Error("請輸入有效的店家當地時間。");
  return date.toISO()!;
}
export const today = (zone: string) =>
  DateTime.now().setZone(zone).toISODate()!;
export const stamp = (value: string, zone: string) =>
  DateTime.fromISO(value).setZone(zone).toFormat("MM/dd HH:mm");

export interface BookingBusiness extends Business {
  currency: string;
}
export interface Service {
  id: string;
  name: string;
  duration_minutes: number;
  price: string;
  is_active: boolean;
}
export interface Staff {
  id: string;
  name: string;
  is_active: boolean;
}
export interface Customer {
  id: string;
  name: string;
  phone: string;
  from_agent: boolean;
}
export interface Booking {
  currency: string;
  id: string;
  customer: { id: string; name: string };
  staff: { id: string; name: string };
  service: { id: string; name: string };
  start: string;
  end: string;
  price: string;
  status: "confirmed" | "cancelled";
  source: "agent" | "staff";
  note: string;
}
export interface Slot {
  start: string;
  end: string;
  staff: { id: string; name: string }[];
}

const bookingErrors: Record<string, string> = {
  slot_unavailable: "此時段已無法預約，請重新查詢。",
  already_booked: "這位顧客已有重疊的預約。",
  in_past: "無法修改已開始的預約。",
  not_reschedulable: "這筆預約目前不能改期。",
  inactive_resource: "服務或人員已停用。",
  booking_conflict: "時段已被預約，請重新查詢。",
};
