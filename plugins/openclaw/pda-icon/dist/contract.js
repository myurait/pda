import { defineFeatureContract } from "openclaw/plugin-sdk/feature-contract";
// このプラグインは、画像の配信 (HTTP ルート) と、画面のコードだけを持つ。
// 呼び出せる操作 (operation) は無いので、空にしている。
// feature の形にしているのは、`openclaw plugins build` / `validate` が受け付けるのが
// tool か feature のプラグインだけで、画面のコード (controlUi) の登録もそこで行われるため。
export const contract = defineFeatureContract({
    pluginId: "pda-icon",
    operations: {},
    events: {},
});
