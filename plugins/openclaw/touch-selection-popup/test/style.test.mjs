import test from "node:test";
import assert from "node:assert/strict";
import { COARSE_POINTER, SELECTION_POPUP_STYLE } from "../dist/style.js";

test("the popup is hidden only under the coarse-pointer media query", () => {
  assert.equal(COARSE_POINTER, "(pointer: coarse)");
  assert.ok(SELECTION_POPUP_STYLE.startsWith(`@media ${COARSE_POINTER} {`));
  assert.match(SELECTION_POPUP_STYLE, /\.chat-selection-popup\s*\{\s*display:\s*none\s*!important;?\s*\}/u);
});

test("the style is one media block, so a desktop browser is not touched", () => {
  assert.equal(SELECTION_POPUP_STYLE.match(/@media/gu)?.length, 1);
  assert.equal(SELECTION_POPUP_STYLE.match(/\{/gu)?.length, 2);
});
