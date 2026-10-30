import { defineFeaturePlugin } from "openclaw/plugin-sdk/feature-plugin";
import { contract } from "./contract.js";
export default defineFeaturePlugin({
    contract,
    name: "Touch Selection Popup",
    description: "Hides the Control UI's \"Add to chat\" selection popup on touch devices.",
    setup() {
        return {};
    },
});
