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

  function textList(title, values) {
    if (!Array.isArray(values) || values.length === 0) return null;
    return h("section", { className: "pda-approval-section" },
      h("h4", null, title),
      h("ul", null, values.map(function (value, index) {
        return h("li", { key: index }, String(value));
      }))
    );
  }

  function ApprovalCard(props) {
    const item = props.item;
    const approval = item.approval || {};
    const finalization = approval.finalization || {};
    const verification = Array.isArray(approval.verification)
      ? approval.verification.map(function (check) {
          return (check.outcome === "passed" ? "✓ " : "× ")
            + (check.command || "確認")
            + (check.summary ? " — " + check.summary : "");
        })
      : [];

    async function approve() {
      const message = [
        "この成果の最終反映を承認しますか？",
        "",
        item.title,
        "HEAD: " + (approval.head_sha || "不明"),
        "影響: " + (approval.impact || "未記載"),
        "",
        "承認後、専用workerが表示された範囲だけを反映します。",
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
          h(CardTitle, null, item.title),
          h(Badge, { variant: item.eligible ? "default" : "destructive" },
            item.eligible ? "検証済み" : "承認不可"
          )
        ),
        h("div", { className: "pda-approval-meta" },
          h("code", null, item.task_id),
          approval.risk_class ? h(Badge, { variant: "outline" }, approval.risk_class) : null,
          approval.head_sha ? h("code", { title: approval.head_sha }, approval.head_sha.slice(0, 12)) : null
        )
      ),
      h(CardContent, null,
        h("p", { className: "pda-approval-outcome" },
          approval.owner_outcome || item.summary || "成果の説明がありません"
        ),
        h("dl", { className: "pda-approval-facts" },
          h("dt", null, "影響"), h("dd", null, approval.impact || "未記載"),
          h("dt", null, "最終反映"), h("dd", null, finalization.kind || "未記載")
        ),
        textList("変更ファイル", approval.changed_files),
        textList("検証", verification),
        textList("反映手順", finalization.steps),
        textList("ロールバック", finalization.rollback),
        textList("残存リスク", approval.residual_risks),
        item.errors && item.errors.length
          ? h("div", { className: "pda-approval-errors" },
              h("strong", null, "承認できない理由"),
              h("ul", null, item.errors.map(function (error, index) {
                return h("li", { key: index }, error);
              }))
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
          h("p", null, "自動改善workerが実装・検証を終えた成果だけを表示します。承認前にはmain反映やサービス変更を行いません。")
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
