import { useState } from "react";
import { useData, type Audit, type Page } from "../api";
import { Alert, Pages } from "../ui";
import { Heading } from "../Heading";

const actionNames: Record<string, string> = {
  "booking.created": "建立預約",
  "booking.rescheduled": "改期",
  "booking.cancelled": "取消預約",
  "booking.listed": "查詢自己的預約",
  "availability.queried": "查詢空檔",
  "shop.read": "查詢預約服務",
  "customer.created": "新增顧客",
  "customer.updated": "更新顧客",
  "service.created": "新增服務",
  "service.updated": "更新服務",
  "staff.created": "新增人員",
  "staff.updated": "更新人員",
  "workinghours.created": "新增工作時間",
  "workinghours.updated": "更新工作時間",
  "workinghours.removed": "移除工作時間",
  "timeoff.created": "新增休息時段",
  "timeoff.updated": "更新休息時段",
  "timeoff.removed": "移除休息時段",
  "bookingsettings.updated": "更新預約設定",
  "agenrena.connect_started": "開始連接 Agenrena",
  "agenrena.connected": "連接 Agenrena",
  "agenrena.disconnected": "中斷 Agenrena 連接",
  "agenrena.message_sent": "送出 Agenrena 通知",
  "agenrena.message_failed": "Agenrena 通知未送達",

  "business.updated": "更新商家資料",
  "member.created": "新增成員",
  "member.updated": "更新成員",
  "agent.key_created": "建立 Agent 金鑰",
  "agent.key_revoked": "撤銷 Agent 金鑰",
  "account.login": "登入",
  "account.logout": "登出",
  "account.password_changed": "更改密碼",
  "owner.initialized": "建立首位擁有者",
  "customer.profile_read": "查詢顧客身分",
  "customer.profile_updated": "更新顧客名稱",
  "business.read": "查詢商家資料",
};
const actorNames: Record<string, string> = {
  agent: "Agent",
  human: "成員",
  system: "系統",
};
export function AuditPage({ timezone }: { timezone: string }) {
  const [page, setPage] = useState(1),
    rows = useData<Page<Audit>>(`audit/?page=${page}`);
  return (
    <>
      <Heading
        eyebrow="ACTIVITY"
        title="操作紀錄"
        description="查看成員的變更，以及 Agent 代表顧客執行的操作。"
      />
      <p className="muted">時間以 {timezone} 顯示</p>
      <Alert message={rows.error?.message} />
      {rows.isPending && <p>載入中…</p>}
      <section className="panel table-wrap">
        <table>
          <thead>
            <tr>
              <th>時間</th>
              <th>操作者</th>
              <th>操作</th>
              <th>紀錄</th>
            </tr>
          </thead>
          <tbody>
            {rows.data?.results.map((e) => (
              <tr key={e.id}>
                <td className="nowrap">
                  {new Date(e.created_at).toLocaleString("zh-TW", {
                    timeZone: timezone,
                    dateStyle: "medium",
                    timeStyle: "short",
                  })}
                </td>
                <td>
                  <strong>{e.actor_label}</strong>
                  <small>{actorNames[e.actor_type] ?? e.actor_type}</small>
                </td>
                <td>{actionNames[e.action] ?? e.action}</td>
                <td>
                  <details>
                    <summary>查看</summary>
                    <small>
                      對象：{e.target_type || "—"} {e.target_id}
                    </small>
                    {e.customer_id && <small>顧客：{e.customer_id}</small>}
                    {e.detail.fields && (
                      <small>變更欄位：{e.detail.fields.join("、")}</small>
                    )}
                    {e.detail.error && <small>原因：{e.detail.error}</small>}
                  </details>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.data?.count === 0 && <p className="empty">尚無操作紀錄。</p>}
        {rows.data && (
          <Pages page={page} pages={rows.data.pages} set={setPage} />
        )}
      </section>
    </>
  );
}
