const RING_RADIUS = 110;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

const ringProgress = document.getElementById('ringProgress');
const timeDisplay = document.getElementById('timeDisplay');
const sessionLabel = document.getElementById('sessionLabel');
const pomodoroDots = document.getElementById('pomodoroDots');
const permissionBanner = document.getElementById('permissionBanner');
const permissionText = document.getElementById('permissionText');

const startBtn = document.getElementById('startBtn');
const pauseBtn = document.getElementById('pauseBtn');
const skipBtn = document.getElementById('skipBtn');

let lastKnownState = {
    active: false,
    session_type: 'work',
    seconds_remaining: 25 * 60,
    duration_seconds: 25 * 60,
    completed_pomodoros: 0,
    paused: false,
};

function mmss(totalSeconds) {
    const safe = Math.max(0, Number(totalSeconds) || 0);
    const m = Math.floor(safe / 60).toString().padStart(2, '0');
    const s = Math.floor(safe % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
}

function updateTimerRing(state) {
    const total = Math.max(1, Number(state.duration_seconds) || 1);
    const remaining = Math.max(0, Number(state.seconds_remaining) || 0);
    const progress = 1 - remaining / total;
    const dashOffset = RING_CIRCUMFERENCE * (1 - progress);

    ringProgress.style.strokeDasharray = `${RING_CIRCUMFERENCE}`;
    ringProgress.style.strokeDashoffset = `${dashOffset}`;
    ringProgress.style.stroke = state.active ? 'var(--accent)' : 'var(--ring-idle)';
}

function updateTimeDisplay(state) {
    const seconds = state.active ? state.seconds_remaining : state.duration_seconds;
    timeDisplay.textContent = mmss(seconds || 0);
}

function updateSessionLabel(state) {
    const type = state.session_type || 'work';
    if (type === 'short_break') {
        sessionLabel.textContent = 'SHORT BREAK';
        return;
    }
    if (type === 'long_break') {
        sessionLabel.textContent = 'LONG BREAK';
        return;
    }
    sessionLabel.textContent = 'FOCUS';
}

function updatePomodorodots(state) {
    const completed = Number(state.completed_pomodoros || 0) % 4;
    let dots = '';
    for (let i = 0; i < 4; i += 1) {
        dots += i < completed ? '●' : '○';
    }
    pomodoroDots.textContent = dots;
}

function updateButtonStates(state) {
    const active = Boolean(state.active);
    const paused = Boolean(state.paused);

    startBtn.disabled = active && !paused;
    pauseBtn.disabled = !active;
    skipBtn.disabled = !active;

    if (!active) {
        pauseBtn.textContent = 'Pause';
    } else {
        pauseBtn.textContent = paused ? 'Resume' : 'Pause';
    }
}

async function postJson(url, body = {}) {
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `Request failed: ${res.status}`);
    }
    return res.json();
}

async function checkPermissions() {
    try {
        const res = await fetch('/api/permissions');
        const p = await res.json();
        const warnings = [];

        if (!p.hosts_writable) {
            warnings.push('Run app with sudo to edit /etc/hosts.');
        }
        if (!p.accessibility) {
            warnings.push('Grant Accessibility for terminal/Python to enable window dimming.');
        }
        if (!p.shortcuts) {
            warnings.push('Install/create macOS Shortcuts for Enable/Disable Do Not Disturb.');
        }

        if (warnings.length > 0) {
            permissionText.textContent = warnings.join(' ');
            permissionBanner.classList.remove('hidden');
        } else {
            permissionBanner.classList.add('hidden');
        }
    } catch (_err) {
        permissionText.textContent = 'Permission check unavailable right now.';
        permissionBanner.classList.remove('hidden');
    }
}

function applyState(state) {
    lastKnownState = { ...lastKnownState, ...state };
    updateTimerRing(lastKnownState);
    updateTimeDisplay(lastKnownState);
    updateSessionLabel(lastKnownState);
    updatePomodorodots(lastKnownState);
    updateButtonStates(lastKnownState);
}

startBtn.addEventListener('click', async () => {
    try {
        const body = { session_type: 'work' };
        const data = await postJson('/session/start', body);
        if (data.state) {
            applyState(data.state);
        }
    } catch (err) {
        console.error(err);
    }
});

pauseBtn.addEventListener('click', async () => {
    try {
        if (lastKnownState.paused) {
            const data = await postJson('/session/resume');
            if (data.state) {
                applyState(data.state);
            }
        } else {
            const data = await postJson('/session/pause');
            if (data.state) {
                applyState(data.state);
            }
        }
    } catch (err) {
        console.error(err);
    }
});

skipBtn.addEventListener('click', async () => {
    try {
        const data = await postJson('/session/skip');
        if (data.state) {
            applyState(data.state);
        }
    } catch (err) {
        console.error(err);
    }
});

const source = new EventSource('/stream');
source.onmessage = (e) => {
    const state = JSON.parse(e.data);
    applyState(state);
};

source.onerror = () => {
    console.warn('SSE disconnected; browser will retry automatically.');
};

checkPermissions();
applyState(lastKnownState);
