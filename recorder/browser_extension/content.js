(() => {
    const seenNodes = new WeakSet();
    let sentCount = 0;

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
        const observer = new MutationObserver(() => collectLinesFromLog(logRoot));
        observer.observe(logRoot, { childList: true, subtree: true });
        setBadge("Recorder bridge: watching");
        return observer;
    }

    async function boot() {
        ensureBadge();
        pokeRecorder("boot");

        let observer = null;
        let activeRoot = null;

        setInterval(() => {
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
