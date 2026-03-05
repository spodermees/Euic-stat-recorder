const DEFAULT_API_URL = "http://127.0.0.1:5000/api/ingest_line";
const DEFAULT_BASE_URL = "http://127.0.0.1:5000";
const QUEUE_KEY = "pendingApiQueue";
const FLUSH_ALARM = "flushPendingApiQueue";
const MAX_QUEUE_SIZE = 2000;

function getSyncStorage(keys) {
    return new Promise((resolve) => {
        chrome.storage.sync.get(keys, (result) => resolve(result || {}));
    });
}

function getLocalStorage(keys) {
    return new Promise((resolve) => {
        chrome.storage.local.get(keys, (result) => resolve(result || {}));
    });
}

function setLocalStorage(values) {
    return new Promise((resolve) => {
        chrome.storage.local.set(values, () => resolve());
    });
}

function getBaseUrlFromIngestUrl(apiUrl) {
    const value = String(apiUrl || "").trim();
    if (!value) return DEFAULT_BASE_URL;
    if (value.includes("/api/ingest_line")) {
        return value.split("/api/ingest_line")[0] || DEFAULT_BASE_URL;
    }
    try {
        const parsed = new URL(value);
        return `${parsed.protocol}//${parsed.host}`;
    } catch (_error) {
        return DEFAULT_BASE_URL;
    }
}

async function getSettings() {
    const data = await getSyncStorage({
        apiUrl: DEFAULT_API_URL,
        enabled: true,
    });
    return {
        apiUrl: String(data.apiUrl || DEFAULT_API_URL).trim() || DEFAULT_API_URL,
        enabled: data.enabled !== false,
    };
}

async function readQueue() {
    const data = await getLocalStorage({ [QUEUE_KEY]: [] });
    return Array.isArray(data[QUEUE_KEY]) ? data[QUEUE_KEY] : [];
}

async function writeQueue(items) {
    const trimmed = Array.isArray(items) ? items.slice(-MAX_QUEUE_SIZE) : [];
    await setLocalStorage({ [QUEUE_KEY]: trimmed });
}

async function enqueue(item) {
    const queue = await readQueue();
    const normalized = {
        id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        createdAt: new Date().toISOString(),
        ...item,
    };
    queue.push(normalized);
    await writeQueue(queue);
    return queue.length;
}

async function getQueueCount() {
    const queue = await readQueue();
    return queue.length;
}

async function trySendItem(item, settings) {
    if (item.type === "line") {
        if (!settings.enabled) {
            return { ok: true, dropped: true };
        }
        const response = await fetch(settings.apiUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ line: item.line }),
            cache: "no-store",
        });
        return { ok: response.ok };
    }

    if (item.type === "replay_bulk") {
        const baseUrl = getBaseUrlFromIngestUrl(settings.apiUrl);
        const endpoint = `${baseUrl}/api/ingest_replay_bulk`;
        const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                urls: item.urls || [],
                team_id: Number(item.teamId),
            }),
            cache: "no-store",
        });
        if (!response.ok) {
            return { ok: false };
        }
        const payload = await response.json().catch(() => ({}));
        return {
            ok: payload.status === "ok",
            payload,
        };
    }

    if (item.type === "poke") {
        const baseUrl = getBaseUrlFromIngestUrl(settings.apiUrl);
        const endpoint = `${baseUrl}/api/poke`;
        const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ source: "extension", reason: item.reason || "unknown" }),
            cache: "no-store",
        });
        return { ok: response.ok };
    }

    return { ok: true };
}

async function flushQueue(limit = 120) {
    const settings = await getSettings();
    const queue = await readQueue();
    if (!queue.length) {
        return { sent: 0, remaining: 0 };
    }

    const pending = [...queue];
    let sent = 0;
    let processed = 0;

    while (pending.length && processed < limit) {
        const item = pending[0];
        processed += 1;
        try {
            const result = await trySendItem(item, settings);
            if (!result.ok) {
                break;
            }
            pending.shift();
            sent += 1;
        } catch (_error) {
            break;
        }
    }

    await writeQueue(pending);
    return { sent, remaining: pending.length };
}

async function sendOrQueueLine(line) {
    const normalized = String(line || "").trim();
    if (!normalized) {
        return { ok: false, reason: "empty-line" };
    }

    const settings = await getSettings();
    if (!settings.enabled) {
        return { ok: true, dropped: true, queued: false, queueCount: await getQueueCount() };
    }

    try {
        const result = await trySendItem({ type: "line", line: normalized }, settings);
        if (result.ok) {
            return { ok: true, sent: true, queued: false, queueCount: await getQueueCount() };
        }
    } catch (_error) {
    }

    const queueCount = await enqueue({ type: "line", line: normalized });
    return { ok: true, sent: false, queued: true, queueCount };
}

async function sendOrQueueReplayBulk(urls, teamId) {
    const cleanedUrls = Array.isArray(urls)
        ? urls.map((item) => String(item || "").trim()).filter(Boolean)
        : [];

    if (!cleanedUrls.length) {
        return { ok: false, reason: "empty-urls" };
    }

    const teamValue = Number(teamId);
    if (!Number.isFinite(teamValue) || teamValue <= 0) {
        return { ok: false, reason: "invalid-team" };
    }

    const settings = await getSettings();
    try {
        const result = await trySendItem({ type: "replay_bulk", urls: cleanedUrls, teamId: teamValue }, settings);
        if (result.ok) {
            return {
                ok: true,
                sent: true,
                queued: false,
                summary: result.payload?.summary || null,
                queueCount: await getQueueCount(),
            };
        }
    } catch (_error) {
    }

    const queueCount = await enqueue({
        type: "replay_bulk",
        urls: cleanedUrls,
        teamId: teamValue,
    });

    return { ok: true, sent: false, queued: true, queueCount };
}

function ensureFlushAlarm() {
    chrome.alarms.create(FLUSH_ALARM, { periodInMinutes: 1 });
}

chrome.runtime.onInstalled.addListener(() => {
    ensureFlushAlarm();
});

chrome.runtime.onStartup.addListener(() => {
    ensureFlushAlarm();
    flushQueue();
});

chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name !== FLUSH_ALARM) return;
    flushQueue();
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    const action = message?.action;

    if (action === "SEND_OR_QUEUE_LINE") {
        sendOrQueueLine(message?.line)
            .then((result) => sendResponse(result))
            .catch(() => sendResponse({ ok: false }));
        return true;
    }

    if (action === "SEND_OR_QUEUE_REPLAY_BULK") {
        sendOrQueueReplayBulk(message?.urls, message?.teamId)
            .then((result) => sendResponse(result))
            .catch(() => sendResponse({ ok: false }));
        return true;
    }

    if (action === "FLUSH_QUEUE_NOW") {
        flushQueue()
            .then((result) => sendResponse({ ok: true, ...result }))
            .catch(() => sendResponse({ ok: false }));
        return true;
    }

    if (action === "QUEUE_STATUS") {
        getQueueCount()
            .then((count) => sendResponse({ ok: true, count }))
            .catch(() => sendResponse({ ok: false, count: 0 }));
        return true;
    }

    if (action === "POKE") {
        getSettings()
            .then((settings) => trySendItem({ type: "poke", reason: message?.reason || "manual" }, settings))
            .then(() => sendResponse({ ok: true }))
            .catch(() => sendResponse({ ok: false }));
        return true;
    }

    return false;
});

ensureFlushAlarm();
flushQueue();
