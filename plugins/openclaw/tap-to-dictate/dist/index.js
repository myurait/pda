import { defineFeaturePlugin } from "openclaw/plugin-sdk/feature-plugin";
import { contract } from "./contract.js";
export default defineFeaturePlugin({
    contract,
    name: "Tap to Dictate",
    description: "Start composer dictation with a single tap on the microphone button.",
    setup() {
        return {};
    },
});
