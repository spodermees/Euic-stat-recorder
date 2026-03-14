(() => {
    const STORAGE_KEY_AUTO_TRACK = "autoTrack";
    const DEFAULT_AUTO_TRACK = true;
    const seenNodes = new WeakSet();
    let sentCount = 0;
    let observer = null;
    let activeRoot = null;
    let autoTrackEnabled = DEFAULT_AUTO_TRACK;

    function sendMessage(message) {
        return new Promise((resolve) => {
            try {
                chrome.runtime.sendMessage(message, (response) => {
                    if (chrome.runtime.lastError) {
                        resolve({ ok: false, error: chrome.runtime.lastError.message });
                        return;
                    }
                    resolve(response || { ok: false });
                });
            } catch (_error) {
                resolve({ ok: false });
            }
        });
    }

    function ensureBadge() {
        let badge = document.getElementById("euic-recorder-bridge-badge");
        if (!badge) {
            badge = document.createElement("div");
            badge.id = "euic-recorder-bridge-badge";
            badge.style.cssText = [
                "position:fixed",
                "bottom:12px",
                "right:12px",
                "padding:6px 10px",
                "background:#1f2538",
                "color:#e6e9f2",
                "border:1px solid #2b334b",
                "border-radius:10px",
                "font:12px/1.2 Segoe UI, sans-serif",
                "z-index:2147483647",
                "pointer-events:none",
                "opacity:0.92"
            ].join(";");
            badge.textContent = "Recorder bridge: idle";
            (document.body || document.documentElement).appendChild(badge);
        }
        return badge;
    }

    function setBadge(text) {
        ensureBadge().textContent = text;
    }

    function cleanLine(text) {
        return String(text || "").replace(/\s+/g, " ").trim();
    }

    function readAutoTrackSetting() {
        return new Promise((resolve) => {
            chrome.storage.sync.get({ [STORAGE_KEY_AUTO_TRACK]: DEFAULT_AUTO_TRACK }, (result) => {
                resolve(result[STORAGE_KEY_AUTO_TRACK] !== false);
            });
        });
    }

    function stopWatching() {
        if (observer) {
            observer.disconnect();
            observer = null;
        }
        activeRoot = null;
    }

    async function pokeRecorder(reason) {
        await sendMessage({ action: "POKE", reason });
    }

    async function sendLine(line) {
        if (!line) {
            return;
        }

        const result = await sendMessage({ action: "SEND_OR_QUEUE_LINE", line });
        if (result?.ok && result?.sent) {
            sentCount += 1;
            setBadge(`Recorder bridge: sent ${sentCount}`);
            return;
        }

        if (result?.ok && result?.queued) {
            setBadge(`Recorder bridge: queued ${result.queueCount}`);
            return;
        }

        if (result?.ok && result?.dropped) {
            setBadge("Recorder bridge: disabled");
            return;
        }

        setBadge("Recorder bridge: error");
    }

    function collectLinesFromLog(logRoot) {
        const lineNodes = logRoot.querySelectorAll(
            ".chat, .chatmessage, .message, .battle-history, .battle-log-message, p, li, div"
        );

        for (const node of lineNodes) {
            if (seenNodes.has(node)) {
                continue;
            }
            seenNodes.add(node);

            const line = cleanLine(node.textContent);
            if (!line || line.length < 2) {
                continue;
            }
            sendLine(line);
        }
    }

    function findLogRoot() {
        return (
            document.querySelector(".battle-log") ||
            document.querySelector(".chatlog") ||
            document.querySelector(".battle-history") ||
            document.querySelector(".chat")
        );
    }

    function watchLogRoot(logRoot) {
        collectLinesFromLog(logRoot);
        const nextObserver = new MutationObserver(() => collectLinesFromLog(logRoot));
        nextObserver.observe(logRoot, { childList: true, subtree: true });
        setBadge("Recorder bridge: watching");
        return nextObserver;
    }

    async function boot() {
        ensureBadge();
        pokeRecorder("boot");

        autoTrackEnabled = await readAutoTrackSetting();
        if (!autoTrackEnabled) {
            stopWatching();
            setBadge("Recorder bridge: auto-track uit");
        }

        chrome.storage.onChanged.addListener((changes, area) => {
            if (area !== "sync" || !changes[STORAGE_KEY_AUTO_TRACK]) {
                return;
            }

            autoTrackEnabled = changes[STORAGE_KEY_AUTO_TRACK].newValue !== false;
            if (!autoTrackEnabled) {
                stopWatching();
                setBadge("Recorder bridge: auto-track uit");
                return;
            }

            setBadge("Recorder bridge: wacht op log");
        });

        setInterval(() => {
            if (!autoTrackEnabled) {
                return;
            }

            const root = findLogRoot();
            if (!root) {
                return;
            }
            if (root === activeRoot) {
                return;
            }

            activeRoot = root;
            if (observer) {
                observer.disconnect();
            }
            observer = watchLogRoot(root);
        }, 1000);
    }

    boot();
})();
