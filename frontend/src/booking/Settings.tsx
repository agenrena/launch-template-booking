import { useState } from "react";
import { DateTime } from "luxon";
import {
  change,
  useData,
  iso,
  stamp,
  type BookingBusiness as Business,
  type Service,
  type Staff,
} from "../api";
import { Alert, Field, Form, Modal, text, useAction } from "../ui";
const weekdays = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"];
interface Hours {
  id: string;
  staff: string;
  weekday: number;
  start: string;
  end: string;
}
interface Off {
  id: string;
  staff: string;
  start: string;
  end: string;
  reason: string;
}
export function Settings({ business }: { business: Business }) {
  const [tab, setTab] = useState("services");
  const action = useAction();
  const [saved, setSaved] = useState(false);
  return (
    <section>
      <div className="section-head">
        <div>
          <h1>服務與排班</h1>
          <p className="muted">每位人員各自設定可預約的工作時間與休息時段。</p>
        </div>
      </div>
      <div className="subnav">
        {[
          ["services", "服務項目"],
          ["staff", "人員與時間"],
        ].map(([id, label]) => (
          <button key={id} aria-pressed={tab === id} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "services" ? (
        <>
          <section className="panel">
            <Form
              busy={action.busy}
              onSubmit={(d) =>
                action.run(async () => {
                  await change("booking-settings/", "PATCH", {
                    currency: text(d, "currency"),
                  });
                  setSaved(true);
                })
              }
            >
              <div className="form-row">
                <Field label="新預約使用的幣別">
                  <input
                    name="currency"
                    defaultValue={business.currency}
                    minLength={3}
                    maxLength={3}
                    required
                    onChange={() => setSaved(false)}
                  />
                </Field>
                <button>儲存幣別</button>
              </div>
              <p className="muted">
                既有預約保留成立時的幣別，不換算歷史金額。
              </p>
              <Alert message={action.error} />
              {saved && <p role="status">已儲存。</p>}
            </Form>
          </section>
          <Services />
        </>
      ) : (
        <People business={business} />
      )}
    </section>
  );
}
function Services() {
  const data = useData<Service[]>("services/"),
    [editing, setEditing] = useState<Service | "new" | null>(null),
    action = useAction();
  return (
    <>
      <div className="section-head">
        <h3>服務項目</h3>
        <button onClick={() => setEditing("new")}>新增服務</button>
      </div>
      <Alert message={data.error?.message || action.error} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>名稱</th>
              <th>時間</th>
              <th>價格</th>
              <th>狀態</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {data.data?.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td>{s.duration_minutes} 分鐘</td>
                <td>{s.price}</td>
                <td>{s.is_active ? "啟用" : "停用"}</td>
                <td>
                  <div className="actions">
                    <button onClick={() => setEditing(s)}>編輯</button>
                    <button
                      disabled={action.busy}
                      onClick={() =>
                        void action.run(() =>
                          change(`services/${s.id}/`, "PATCH", {
                            is_active: !s.is_active,
                          }),
                        )
                      }
                    >
                      {s.is_active ? "停用" : "啟用"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.data?.length === 0 && (
        <p className="empty">新增第一項服務，設定時長與價格。</p>
      )}
      {editing && (
        <ServiceEditor service={editing} close={() => setEditing(null)} />
      )}
    </>
  );
}
function ServiceEditor({
  service,
  close,
}: {
  service: Service | "new";
  close: () => void;
}) {
  const row = service === "new" ? null : service,
    action = useAction();
  return (
    <Modal title={row ? "編輯服務" : "新增服務"} close={close}>
      <Form
        busy={action.busy}
        onSubmit={(data) =>
          action.run(async () => {
            await change(
              `services/${row ? row.id + "/" : ""}`,
              row ? "PATCH" : "POST",
              {
                name: text(data, "name"),
                duration_minutes: Number(data.get("duration_minutes")),
                price: text(data, "price"),
              },
            );
            close();
          })
        }
      >
        <Field label="名稱">
          <input
            name="name"
            defaultValue={row?.name}
            maxLength={120}
            required
          />
        </Field>
        <Field label="時間（分鐘）">
          <input
            name="duration_minutes"
            type="number"
            min={5}
            max={1440}
            defaultValue={row?.duration_minutes ?? 30}
            required
          />
        </Field>
        <Field label="價格">
          <input
            name="price"
            type="number"
            min={0}
            max={99999999.99}
            step="0.01"
            defaultValue={row?.price ?? "0"}
            required
          />
        </Field>
        <Alert message={action.error} />
        <button className="primary">儲存</button>
      </Form>
    </Modal>
  );
}
function People({ business }: { business: Business }) {
  const staff = useData<Staff[]>("staff/"),
    hours = useData<Hours[]>("hours/"),
    off = useData<Off[]>("time-off/"),
    action = useAction();
  const [selected, setSelected] = useState(""),
    [editing, setEditing] = useState<Staff | "new" | null>(null);
  const person = staff.data?.find((s) => s.id === selected);
  return (
    <>
      <div className="section-head">
        <h3>人員與可預約時間</h3>
        <button onClick={() => setEditing("new")}>新增人員</button>
      </div>
      <Field label="人員">
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          <option value="">選擇人員</option>
          {staff.data?.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
              {s.is_active ? "" : "（停用）"}
            </option>
          ))}
        </select>
      </Field>
      <Alert
        message={
          staff.error?.message ||
          hours.error?.message ||
          off.error?.message ||
          action.error
        }
      />
      {person && (
        <>
          <div className="actions">
            <button onClick={() => setEditing(person)}>編輯姓名</button>
            <button
              disabled={action.busy}
              onClick={() =>
                void action.run(() =>
                  change(`staff/${person.id}/`, "PATCH", {
                    is_active: !person.is_active,
                  }),
                )
              }
            >
              {person.is_active ? "停用人員" : "啟用人員"}
            </button>
          </div>
          <h3>每週工作時間</h3>
          <p className="muted">
            以 {business.timezone}{" "}
            為準。沒有設定時間的日期不接受預約；午休可分成上午、下午兩段。
          </p>
          <div className="list">
            {hours.data
              ?.filter((h) => h.staff === selected)
              .map((h) => (
                <div className="list-row" key={h.id}>
                  <span>
                    {weekdays[h.weekday]} {h.start.slice(0, 5)}–
                    {h.end.slice(0, 5)}
                  </span>
                  <button
                    disabled={action.busy}
                    onClick={() =>
                      void action.run(() => change(`hours/${h.id}/`, "DELETE"))
                    }
                  >
                    移除
                  </button>
                </div>
              ))}
          </div>
          <Form
            busy={action.busy}
            onSubmit={(data) =>
              action.run(() =>
                change("hours/", "POST", {
                  staff: selected,
                  weekday: Number(data.get("weekday")),
                  start: text(data, "start"),
                  end: text(data, "end"),
                }),
              )
            }
          >
            <div className="form-row">
              <Field label="星期">
                <select name="weekday">
                  {weekdays.map((d, i) => (
                    <option key={d} value={i}>
                      {d}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="開始">
                <input name="start" type="time" defaultValue="09:00" required />
              </Field>
              <Field label="結束">
                <input name="end" type="time" defaultValue="17:00" required />
              </Field>
              <button>新增時段</button>
            </div>
          </Form>
          <h3>不可預約時段</h3>
          <p className="muted">
            休假或臨時休息。新增後不會自動取消既有預約，請自行確認日曆。
          </p>
          <div className="list">
            {off.data
              ?.filter(
                (o) =>
                  o.staff === selected &&
                  DateTime.fromISO(o.end) > DateTime.now(),
              )
              .map((o) => (
                <div className="list-row" key={o.id}>
                  <span>
                    {stamp(o.start, business.timezone)}–
                    {stamp(o.end, business.timezone)} {o.reason}
                  </span>
                  <button
                    disabled={action.busy}
                    onClick={() =>
                      void action.run(() =>
                        change(`time-off/${o.id}/`, "DELETE"),
                      )
                    }
                  >
                    移除
                  </button>
                </div>
              ))}
          </div>
          <Form
            busy={action.busy}
            onSubmit={(data) =>
              action.run(() =>
                change("time-off/", "POST", {
                  staff: selected,
                  start: iso(text(data, "start"), business.timezone),
                  end: iso(text(data, "end"), business.timezone),
                  reason: text(data, "reason"),
                }),
              )
            }
          >
            <div className="form-row">
              <Field label="開始">
                <input name="start" type="datetime-local" required />
              </Field>
              <Field label="結束">
                <input name="end" type="datetime-local" required />
              </Field>
            </div>
            <Field label="原因">
              <input name="reason" maxLength={200} />
            </Field>
            <button>新增休息時段</button>
          </Form>
        </>
      )}
      {!staff.data?.length && (
        <p className="empty">新增服務人員後，設定他可以接受預約的時間。</p>
      )}
      {editing && (
        <PersonEditor person={editing} close={() => setEditing(null)} />
      )}
    </>
  );
}
function PersonEditor({
  person,
  close,
}: {
  person: Staff | "new";
  close: () => void;
}) {
  const row = person === "new" ? null : person,
    action = useAction();
  return (
    <Modal title={row ? "編輯人員" : "新增人員"} close={close}>
      <Form
        busy={action.busy}
        onSubmit={(data) =>
          action.run(async () => {
            await change(
              `staff/${row ? row.id + "/" : ""}`,
              row ? "PATCH" : "POST",
              { name: text(data, "name") },
            );
            close();
          })
        }
      >
        <Field label="姓名">
          <input
            name="name"
            defaultValue={row?.name}
            maxLength={120}
            required
          />
        </Field>
        <Alert message={action.error} />
        <button className="primary">儲存</button>
      </Form>
    </Modal>
  );
}
