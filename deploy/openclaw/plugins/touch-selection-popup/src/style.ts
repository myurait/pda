/**
 * Kept apart from the DOM code so it can be tested without a browser.
 */

export const COARSE_POINTER = "(pointer: coarse)";

// The host builds .chat-selection-popup itself when text inside a message is
// selected. Hiding it with a style rule leaves the host's state and the system's
// own selection menu alone.
export const SELECTION_POPUP_STYLE = `@media ${COARSE_POINTER} { .chat-selection-popup { display: none !important; } }`;
