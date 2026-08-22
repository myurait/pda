(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__) return;

  const React = SDK.React;
  const { useCallback, useEffect, useState } = SDK.hooks;
  const {
    Badge,
    Button,
    Card,
    CardContent,
    CardHeader,
    CardTitle,
  } = SDK.components;
  const h = React.createElement;
  const rawBasePath = window.__HERMES_BASE_PATH__ || "";
  const basePath = rawBasePath
    ? (rawBasePath.startsWith("/") ? rawBasePath : "/" + rawBasePath).replace(/\/+$/, "")
    : "";

  function ApprovalCard(props) {
    const item = props.item;
    const ownerMessage = item.owner_message || {};

    async function approve() {
      const message = [
        "承認依頼です。",
        "",
        "承認対象: " + (ownerMessage.approval_subject || "未記載"),
        "目的・成果: " + (ownerMessage.purpose || "未記載"),
        "承認後の変化: " + (ownerMessage.changes_after_approval || "未記載"),
        "主要リスクと可逆性: " + (ownerMessage.risk_and_reversibility || "未記載"),
        "推奨: " + (ownerMessage.recommendation || "未記載"),
        "必要な操作: " + (ownerMessage.action || "未記載"),
      ].join("\n");
      if (!window.confirm(message)) return;
      await props.onAction(
        "/api/plugins/pda-approvals/tasks/" + encodeURIComponent(item.task_id) + "/approve",
        { digest: item.digest }
      );
    }

    async function requestChanges() {
      const reason = window.prompt("差戻し理由を具体的に入力してください");
      if (!reason || !reason.trim()) return;
      await props.onAction(
        "/api/plugins/pda-approvals/tasks/" + encodeURIComponent(item.task_id) + "/request-changes",
        { reason: reason.trim() }
      );
    }

    return h(Card, { className: "pda-approval-card" },
      h(CardHeader, null,
        h("div", { className: "pda-approval-title-row" },
          h(CardTitle, null, ownerMessage.approval_subject || "承認文面の再作成が必要です"),
          h(Badge, { variant: item.eligible ? "default" : "destructive" },
            item.eligible ? "検証済み" : "承認不可"
          )
        )
      ),
      h(CardContent, null,
        h("dl", { className: "pda-approval-facts" },
          h("dt", null, "目的・得られる成果"),
          h("dd", null, ownerMessage.purpose || "未記載"),
          h("dt", null, "承認後に変わること"),
          h("dd", null, ownerMessage.changes_after_approval || "未記載"),
          h("dt", null, "主要リスクと可逆性"),
          h("dd", null, ownerMessage.risk_and_reversibility || "未記載"),
          h("dt", null, "推奨"),
          h("dd", null, ownerMessage.recommendation || "未記載"),
          h("dt", null, "必要な操作"),
          h("dd", null, ownerMessage.action || "未記載")
        ),
        item.blocking_reason
          ? h("div", { className: "pda-approval-errors" },
              h("strong", null, "承認できない理由"),
              h("p", null, item.blocking_reason)
            )
          : null,
        h("div", { className: "pda-approval-actions" },
          h(Button, { variant: "outline", onClick: requestChanges }, "差戻し"),
          h(Button, { disabled: !item.eligible, onClick: approve }, "最終反映を承認")
        )
      )
    );
  }

  function usePendingApprovals() {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const load = useCallback(async function () {
      try {
        const data = await SDK.fetchJSON("/api/plugins/pda-approvals/pending");
        setItems(Array.isArray(data.items) ? data.items : []);
        setError("");
      } catch (err) {
        setError(err && err.message ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    }, []);

    useEffect(function () {
      load();
      const timer = window.setInterval(load, 30000);
      return function () { window.clearInterval(timer); };
    }, [load]);

    return { items: items, loading: loading, error: error, reload: load };
  }

  function ApprovalPage() {
    const state = usePendingApprovals();
    const [actionError, setActionError] = useState("");

    async function act(url, body) {
      try {
        await SDK.fetchJSON(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        setActionError("");
        await state.reload();
      } catch (err) {
        setActionError(err && err.message ? err.message : String(err));
      }
    }

    return h("div", { className: "pda-approvals-page" },
      h("div", { className: "pda-approvals-heading" },
        h("div", null,
          h("h1", null, "PDA 最終承認"),
          h("p", null, "判断に必要な成果、変化、主要リスク、必要な操作だけを表示します。承認前には通常環境へ反映しません。")
        ),
        h(Button, { variant: "outline", onClick: state.reload }, "再読込")
      ),
      state.error || actionError
        ? h("div", { className: "pda-approval-errors" }, state.error || actionError)
        : null,
      state.loading
        ? h("p", { className: "text-muted-foreground" }, "承認待ちを読み込んでいます…")
        : state.items.length === 0
          ? h(Card, null, h(CardContent, { className: "pda-approvals-empty" }, "現在、最終承認待ちはありません。"))
          : h("div", { className: "pda-approvals-grid" },
              state.items.map(function (item) {
                return h(ApprovalCard, { key: item.task_id, item: item, onAction: act });
              })
            )
    );
  }

  function ApprovalBadge() {
    const state = usePendingApprovals();
    const count = state.items.length;
    return h("a", {
      href: basePath + "/pda-approvals",
      className: "pda-approval-header-link",
      title: "PDAの最終承認待ち",
    }, "承認", h(Badge, { variant: count ? "destructive" : "outline" }, String(count)));
  }

  window.__HERMES_PLUGINS__.register("pda-approvals", ApprovalPage);
  window.__HERMES_PLUGINS__.registerSlot("pda-approvals", "header-right", ApprovalBadge);
})();
