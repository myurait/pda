/**
 * Keeps one microphone stream open between dictations, so that the browser is
 * asked for the microphone once, not before every dictation.
 *
 * The host acquires the microphone with getUserMedia for every dictation and
 * stops the tracks when the dictation ends. WebKit (iOS) remembers a grant only
 * for the page, drops it after the capture has been idle for a while, and keeps
 * it for a long time only while a capture is running. A Home Screen web app
 * cannot use Safari's saved "Allow" either, so the prompt returns each time.
 *
 * Here getUserMedia (audio only) hands the caller a clone of a track that this
 * module keeps alive. A clone shares the capture source: the caller stopping its
 * clone does not end the capture, and the next dictation gets a new clone with
 * no getUserMedia call. The kept track is released after `holdMs` without a
 * caller, when the page is hidden for good (pagehide), or when it is no longer
 * live. `holdMs` of 0 or less turns the whole thing off.
 */
export const HOLD_MINUTES_KEY = "tap-to-dictate:mic-hold-minutes";
export const DEFAULT_HOLD_MINUTES = 30;
// Minutes from a stored value; anything but a finite number falls back to the default.
export function parseHoldMinutes(raw) {
    if (raw === null || raw === undefined || raw.trim() === "")
        return DEFAULT_HOLD_MINUTES;
    const minutes = Number(raw);
    return Number.isFinite(minutes) ? minutes : DEFAULT_HOLD_MINUTES;
}
// Only a plain audio request is kept; a video request, or no audio, passes through.
function audioKey(constraints) {
    if (!constraints || !constraints.audio || constraints.video)
        return null;
    const audio = constraints.audio;
    return JSON.stringify(audio);
}
export function installMicKeeper(mediaDevices, readHoldMinutes, pageEvents = window) {
    const original = mediaDevices.getUserMedia;
    const hadOwn = Object.prototype.hasOwnProperty.call(mediaDevices, "getUserMedia");
    const callOriginal = (constraints) => original.call(mediaDevices, constraints);
    let keeper = null;
    let pending = null;
    const isUsable = (candidate, key) => candidate !== null &&
        candidate.key === key &&
        candidate.track.readyState === "live" &&
        !candidate.track.muted;
    const release = (target) => {
        if (!target)
            return;
        if (target.idleTimer !== null)
            clearTimeout(target.idleTimer);
        target.idleTimer = null;
        target.track.stop();
        if (keeper === target)
            keeper = null;
    };
    const armIdleTimer = (target) => {
        if (target.idleTimer !== null)
            clearTimeout(target.idleTimer);
        target.idleTimer = null;
        if (target.clones.size > 0)
            return;
        const holdMs = readHoldMinutes() * 60_000;
        target.idleTimer = setTimeout(() => release(target), holdMs);
    };
    const lend = (target) => {
        if (target.idleTimer !== null)
            clearTimeout(target.idleTimer);
        target.idleTimer = null;
        const clone = target.track.clone();
        clone.enabled = true;
        target.clones.add(clone);
        const stop = clone.stop.bind(clone);
        clone.stop = () => {
            stop();
            if (target.clones.delete(clone))
                armIdleTimer(target);
        };
        return new MediaStream([clone]);
    };
    const acquire = (key, constraints) => {
        if (pending?.key === key)
            return pending.promise;
        const promise = callOriginal(constraints).then((stream) => {
            const [track] = stream.getAudioTracks();
            if (!track)
                throw new DOMException("No audio track", "NotFoundError");
            // The new capture is running before the old one is released, so the
            // browser still sees a capture in progress.
            const previous = keeper;
            const created = { key, track, clones: new Set(), idleTimer: null };
            keeper = created;
            track.addEventListener("ended", () => {
                if (keeper === created)
                    keeper = null;
            });
            // A previous keeper still lent out is released when its last clone stops.
            if (previous && previous.clones.size === 0)
                release(previous);
            return created;
        });
        const entry = { key, promise };
        pending = entry;
        const clear = () => {
            if (pending === entry)
                pending = null;
        };
        promise.then(clear, clear);
        return promise;
    };
    const getUserMedia = async (constraints) => {
        const key = audioKey(constraints);
        if (key === null || !(readHoldMinutes() > 0))
            return callOriginal(constraints);
        if (isUsable(keeper, key))
            return lend(keeper);
        return lend(await acquire(key, constraints));
    };
    Object.defineProperty(mediaDevices, "getUserMedia", {
        configurable: true,
        writable: true,
        value: getUserMedia,
    });
    const onPageHide = (event) => {
        // A page kept in the back/forward cache comes back with ended tracks; the
        // next request then acquires again, so only a real unload needs the stop.
        if (event.persisted)
            return;
        release(keeper);
    };
    pageEvents.addEventListener("pagehide", onPageHide);
    return {
        dispose() {
            pageEvents.removeEventListener("pagehide", onPageHide);
            release(keeper);
            if (hadOwn) {
                Object.defineProperty(mediaDevices, "getUserMedia", {
                    configurable: true,
                    writable: true,
                    value: original,
                });
            }
            else {
                delete mediaDevices.getUserMedia;
            }
        },
    };
}
