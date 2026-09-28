import { useData, type Business } from "../api";
import { Alert } from "../ui";
import { CalendarPage } from "./Calendar";
import { Settings } from "./Settings";
export function BookingWorkspace({
  business,
  page,
}: {
  business: Business;
  page: "calendar" | "catalog";
}) {
  const settings = useData<{ currency: string }>("booking-settings/");
  if (settings.error) return <Alert message={settings.error.message} />;
  if (!settings.data) return <p>載入預約設定…</p>;
  const value = { ...business, currency: settings.data.currency };
  return page === "calendar" ? (
    <CalendarPage business={value} />
  ) : (
    <Settings business={value} />
  );
}
