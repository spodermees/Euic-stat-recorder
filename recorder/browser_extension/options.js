const DEFAULT_API_URL = "http://127.0.0.1:5000/api/ingest_line";
const STORAGE_KEY_AUTO_TRACK = "autoTrack";

function getStorage(keys) {
    return new Promise((resolve) => {
        chrome.storage.sync.get(keys, (result) => resolve(result || {}));
    });
}

function setStorage(values) {
    return new Promise((resolve) => {
        chrome.storage.sync.set(values, () => resolve());
    });
}

async function restore() {
    const data = await getStorage({
        apiUrl: DEFAULT_API_URL,
        enabled: true,
        [STORAGE_KEY_AUTO_TRACK]: true,
    });

    document.getElementById("apiUrl").value = data.apiUrl || DEFAULT_API_URL;
    document.getElementById("enabled").checked = data.enabled !== false;
    document.getElementById("autoTrack").checked = data[STORAGE_KEY_AUTO_TRACK] !== false;
}

function showStatus(text) {
    const status = document.getElementById("status");
    status.textContent = text;
    setTimeout(() => {
        status.textContent = "";
    }, 1600);
}

async function save() {
    const apiUrl = (document.getElementById("apiUrl").value || "").trim() || DEFAULT_API_URL;
    const enabled = document.getElementById("enabled").checked;
    const autoTrack = document.getElementById("autoTrack").checked;

    await setStorage({ apiUrl, enabled, [STORAGE_KEY_AUTO_TRACK]: autoTrack });
    showStatus("Instellingen opgeslagen.");
}

document.getElementById("save").addEventListener("click", save);
restore();
