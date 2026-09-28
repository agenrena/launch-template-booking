import { useState } from "react";
import { change, useData, type Customer, type Page } from "../api";
import { Alert, Field, Form, Modal, Pages, text, useAction } from "../ui";
export function Customers() {
  const [q, setQ] = useState(""),
    [page, setPage] = useState(1),
    [editing, setEditing] = useState<Customer | "new" | null>(null);
  const customers = useData<Page<Customer>>(
    `customers/?q=${encodeURIComponent(q)}&page=${page}`,
  );
  return (
    <section>
      <div className="section-head">
        <h2>顧客</h2>
        <button className="primary" onClick={() => setEditing("new")}>
          新增顧客
        </button>
      </div>
      <input
        aria-label="搜尋顧客"
        placeholder="搜尋姓名或電話"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setPage(1);
        }}
      />
      <Alert message={customers.error?.message} />
      {customers.isPending && <p>載入中…</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>姓名</th>
              <th>電話</th>
              <th>來源</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {customers.data?.results.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.phone || "—"}</td>
                <td>{c.from_agent ? "Agenrena" : "店家"}</td>
                <td>
                  <button onClick={() => setEditing(c)}>編輯</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {customers.data?.count === 0 && (
        <p className="empty">
          還沒有符合的顧客。可以手動新增，也會在 Agent 第一次預約時建立。
        </p>
      )}
      {customers.data && (
        <Pages page={page} pages={customers.data.pages} set={setPage} />
      )}
      {editing && (
        <CustomerEditor customer={editing} close={() => setEditing(null)} />
      )}
    </section>
  );
}
function CustomerEditor({
  customer,
  close,
}: {
  customer: Customer | "new";
  close: () => void;
}) {
  const action = useAction(),
    current = customer === "new" ? null : customer;
  return (
    <Modal title={current ? "編輯顧客" : "新增顧客"} close={close}>
      <Form
        busy={action.busy}
        onSubmit={(data) =>
          action.run(async () => {
            await change(
              `customers/${current ? `${current.id}/` : ""}`,
              current ? "PATCH" : "POST",
              { name: text(data, "name"), phone: text(data, "phone") },
            );
            close();
          })
        }
      >
        <Field label="姓名">
          <input
            name="name"
            defaultValue={current?.name}
            maxLength={120}
            required
          />
        </Field>
        <Field label="電話">
          <input name="phone" defaultValue={current?.phone} maxLength={40} />
        </Field>
        <Alert message={action.error} />
        <button className="primary">儲存</button>
      </Form>
    </Modal>
  );
}
