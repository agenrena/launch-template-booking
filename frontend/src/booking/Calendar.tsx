import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import FullCalendar from "@fullcalendar/react";
import timeGrid from "@fullcalendar/timegrid";
import interaction from "@fullcalendar/interaction";
import luxon from "@fullcalendar/luxon3";
import zh from "@fullcalendar/core/locales/zh-tw";
import { DateTime } from "luxon";
import {
  api,
  change,
  useData,
  today,
  stamp,
  type Booking,
  type BookingBusiness as Business,
  type Customer,
  type Service,
  type Page,
  type Slot,
} from "../api";
import { Alert, Field, Modal, Pages, useAction } from "../ui";

export function CalendarPage({ business }: { business: Business }) {
  const [range, setRange] = useState({
    first: today(business.timezone),
    last: today(business.timezone),
  });
  const [editing, setEditing] = useState<Booking | "new" | null>(null);
  const query = useQuery({
    queryKey: ["calendar", range],
    queryFn: async () => {
      const path = `bookings/?date_from=${range.first}&date_to=${range.last}`;
      const first = await api<Page<Booking>>(path);
      const rows = [...first.results];
      for (let page = 2; page <= first.pages; page++)
        rows.push(
          ...(await api<Page<Booking>>(`${path}&page=${page}`)).results,
        );
      return rows;
    },
  });
  return (
    <section>
      <div className="section-head">
        <div>
          <h2>預約日曆</h2>
          <p className="muted">{business.timezone} · ◆ 表示 Agent 建立的預約</p>
        </div>
        <button className="primary" onClick={() => setEditing("new")}>
          新增預約
        </button>
      </div>
      <Alert message={query.error?.message} />
      {query.isFetching && (
        <p className="muted" role="status">
          更新日曆中…
        </p>
      )}
      <FullCalendar
        plugins={[timeGrid, interaction, luxon]}
        locale={zh}
        timeZone={business.timezone}
        initialView={
          window.matchMedia("(max-width: 640px)").matches
            ? "timeGridDay"
            : "timeGridWeek"
        }
        headerToolbar={{
          left: "prev,next today",
          center: "title",
          right: "timeGridDay,timeGridWeek",
        }}
        allDaySlot={false}
        // A fixed height gives the day its own scroll area, so it opens at
        // scrollTime instead of midnight while late bookings stay reachable.
        height="75vh"
        slotMinTime="00:00:00"
        scrollTime="08:00:00"
        slotMaxTime="24:00:00"
        nowIndicator
        datesSet={(arg) => {
          const first = arg.startStr.slice(0, 10),
            last = DateTime.fromISO(arg.endStr).minus({ days: 1 }).toISODate()!;
          setRange((previous) =>
            previous.first === first && previous.last === last
              ? previous
              : { first, last },
          );
        }}
        events={(query.data ?? [])
          .filter((b) => b.status === "confirmed")
          .map((b) => ({
            id: b.id,
            start: b.start,
            end: b.end,
            title: `${b.source === "agent" ? "◆ " : ""}${b.customer.name} · ${b.service.name} · ${b.staff.name}`,
          }))}
        eventClick={(arg) =>
          setEditing(query.data!.find((b) => b.id === arg.event.id)!)
        }
      />
      <details className="cancelled">
        <summary>
          已取消的預約（
          {query.data?.filter((b) => b.status === "cancelled").length ?? 0}）
        </summary>
        {query.data
          ?.filter((b) => b.status === "cancelled")
          .map((b) => (
            <p key={b.id}>
              {stamp(b.start, business.timezone)} · {b.customer.name} ·{" "}
              {b.service.name}
            </p>
          ))}
      </details>
      {editing && (
        <BookingEditor
          key={typeof editing === "string" ? editing : editing.id}
          booking={editing}
          business={business}
          close={() => setEditing(null)}
        />
      )}
    </section>
  );
}
function BookingEditor({
  booking,
  business,
  close,
}: {
  booking: Booking | "new";
  business: Business;
  close: () => void;
}) {
  const current = booking === "new" ? null : booking;
  const services = useData<Service[]>("services/");
  const [service, setService] = useState(current?.service.id ?? "");
  const [date, setDate] = useState(
    current
      ? DateTime.fromISO(current.start).setZone(business.timezone).toISODate()!
      : today(business.timezone),
  );
  const [slot, setSlot] = useState(""),
    [page, setPage] = useState(1);
  const [search, setSearch] = useState(""),
    [customer, setCustomer] = useState(""),
    [newCustomer, setNewCustomer] = useState(false),
    [name, setName] = useState(""),
    [phone, setPhone] = useState(""),
    [note, setNote] = useState("");
  const [confirmCancel, setConfirmCancel] = useState(false);
  const customers = useData<Page<Customer>>(
    `customers/?q=${encodeURIComponent(search)}`,
  );
  const action = useAction();
  const slots = useQuery({
    queryKey: ["slots", service, date, page, current?.id],
    enabled: !!service && !!date,
    queryFn: () =>
      api<{ slots: Slot[]; pages: number }>(
        `availability/?service=${service}&date_from=${date}&page=${page}${current ? `&booking_id=${current.id}` : ""}`,
      ),
  });
  const past = current && new Date(current.start) <= new Date();
  const serviceInfo = services.data?.find((s) => s.id === service);
  async function save() {
    const [start, staff_id] = JSON.parse(slot) as [string, string];
    if (current)
      await change(`bookings/${current.id}/`, "PATCH", { start, staff_id });
    else {
      const customer_id = newCustomer
        ? (await change<Customer>("customers/", "POST", { name, phone })).id
        : customer;
      // Keep a just-created customer selected if the chosen slot was taken meanwhile.
      if (newCustomer) {
        setCustomer(customer_id);
        setNewCustomer(false);
      }
      await change("bookings/", "POST", {
        service,
        staff_id,
        start,
        customer_id,
        note,
      });
    }
    close();
  }
  return (
    <Modal title={current ? "預約詳情" : "新增預約"} close={close}>
      {current && (
        <div className="booking-summary">
          <strong>
            {current.customer.name} · {current.service.name}
          </strong>
          <p>
            {stamp(current.start, business.timezone)} —{" "}
            {stamp(current.end, business.timezone)} · {current.staff.name}
          </p>
          <p>
            {current.currency} {current.price} ·{" "}
            {current.source === "agent" ? "Agent 建立" : "店家建立"}
          </p>
          {current.note && <p>{current.note}</p>}
        </div>
      )}
      {past ? (
        <p className="muted">這筆預約已開始，保留紀錄供查閱。</p>
      ) : (
        <fieldset disabled={action.busy}>
          {current && <p className="muted">改期保留原服務時長、報價與幣別。</p>}
          {!current && (
            <>
              <Field label="服務">
                <select
                  value={service}
                  onChange={(e) => {
                    setService(e.target.value);
                    setSlot("");
                    setPage(1);
                  }}
                  required
                >
                  <option value="">選擇服務</option>
                  {services.data
                    ?.filter((s) => s.is_active)
                    .map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name} · {s.duration_minutes} 分鐘 ·{" "}
                        {business.currency} {s.price}
                      </option>
                    ))}
                </select>
              </Field>
              <label className="check">
                <input
                  type="checkbox"
                  checked={newCustomer}
                  onChange={(e) => setNewCustomer(e.target.checked)}
                />{" "}
                新顧客
              </label>
              {newCustomer ? (
                <>
                  <Field label="顧客姓名">
                    <input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      maxLength={120}
                    />
                  </Field>
                  <Field label="電話">
                    <input
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      maxLength={40}
                    />
                  </Field>
                </>
              ) : (
                <>
                  <Field label="搜尋顧客">
                    <input
                      placeholder="輸入姓名或電話"
                      value={search}
                      onChange={(e) => {
                        setSearch(e.target.value);
                        setCustomer("");
                      }}
                    />
                  </Field>
                  <Field label="顧客">
                    <select
                      value={customer}
                      onChange={(e) => setCustomer(e.target.value)}
                    >
                      <option value="">選擇顧客</option>
                      {customer &&
                        !customers.data?.results.some(
                          (c) => c.id === customer,
                        ) && (
                          <option value={customer}>
                            {name || "已選擇的顧客"}
                          </option>
                        )}
                      {customers.data?.results.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name} {c.phone}
                        </option>
                      ))}
                    </select>
                  </Field>
                  {(customers.data?.pages ?? 0) > 1 && (
                    <p className="muted">
                      請輸入更完整的姓名或電話縮小搜尋範圍。
                    </p>
                  )}
                </>
              )}
              <Field label="備註">
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  maxLength={2000}
                />
              </Field>
            </>
          )}
          <Field
            label={`${current ? "改期日期" : "日期"}（${business.timezone}）`}
          >
            <input
              type="date"
              min={today(business.timezone)}
              value={date}
              onChange={(e) => {
                setDate(e.target.value);
                setSlot("");
                setPage(1);
              }}
            />
          </Field>
          {slots.isFetching && <p role="status">查詢空檔中…</p>}
          <Field label="可預約時段與人員">
            <select
              value={slot}
              onChange={(e) => setSlot(e.target.value)}
              disabled={!service || slots.isFetching}
            >
              <option value="">選擇時段</option>
              {slots.data?.slots.flatMap((s) =>
                s.staff.map((person) => (
                  <option
                    key={s.start + person.id}
                    value={JSON.stringify([s.start, person.id])}
                  >
                    {stamp(s.start, business.timezone)} · {person.name}
                  </option>
                )),
              )}
            </select>
          </Field>
          {slots.data?.slots.length === 0 && (
            <p className="empty">
              當天沒有空檔，請換一天。請確認已設定人員與工作時間。
            </p>
          )}
          {slots.data && (
            <Pages
              page={page}
              pages={slots.data.pages}
              set={(p) => {
                setPage(p);
                setSlot("");
              }}
            />
          )}
          {serviceInfo && !current && (
            <p className="muted">
              {serviceInfo.duration_minutes} 分鐘 · {business.currency}{" "}
              {serviceInfo.price}
            </p>
          )}
          <div className="actions">
            <button
              className="primary"
              disabled={
                !slot || (!current && !(newCustomer ? name.trim() : customer))
              }
              onClick={() => void action.run(save)}
            >
              {current ? "確認改期" : "建立預約"}
            </button>
            {current && (
              <button className="danger" onClick={() => setConfirmCancel(true)}>
                取消這筆預約
              </button>
            )}
          </div>
          {confirmCancel && (
            <div className="confirm">
              <p>
                確定取消這筆預約？若已連接 Agenrena，透過 Agenrena
                預約的顧客會在對話中收到取消通知。
              </p>
              <div className="actions">
                <button
                  className="danger"
                  onClick={() =>
                    void action.run(async () => {
                      await change(
                        `bookings/${current!.id}/cancel/`,
                        "POST",
                        {},
                      );
                      close();
                    })
                  }
                >
                  確定取消
                </button>
                <button onClick={() => setConfirmCancel(false)}>
                  保留預約
                </button>
              </div>
            </div>
          )}
        </fieldset>
      )}
      <Alert
        message={
          action.error ||
          slots.error?.message ||
          services.error?.message ||
          customers.error?.message
        }
      />
    </Modal>
  );
}
