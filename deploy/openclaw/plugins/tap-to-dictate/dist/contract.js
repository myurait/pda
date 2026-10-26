import { defineFeatureContract } from "openclaw/plugin-sdk/feature-contract";
// This plugin only changes how the composer microphone button reacts to a tap.
// It has no backend operations; the contract exists so the plugin id is shared
// between the backend entry and the Control UI entry.
export const contract = defineFeatureContract({
    pluginId: "tap-to-dictate",
    operations: {},
    events: {},
});
