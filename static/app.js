const RING_RADIUS = 110;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

const ringProgress = document.getElementById('ringProgress');
const timeDisplay = document.getElementById('timeDisplay');
const sessionLabel = document.getElementById('sessionLabel');
const pomodoroDots = document.getElementById('pomodoroDots');
const permissionBanner = document.getElementById('permissionBanner');
const permissionText = document.getElementById('permissionText');
const timerStatus = document.getElementById('timerStatus');

const startBtn = document.getElementById('startBtn');
const pauseBtn = document.getElementById('pauseBtn');
const skipBtn = document.getElementById('skipBtn');
const timerCard = document.getElementById('timerCard');

let lastKnownState = {
    active: false,
    session_type: 'work',
    next_session_type: 'work',
    seconds_remaining: 25 * 60,
    duration_seconds: 25 * 60,
    completed_pomodoros: 0,
    paused: false,
};

let cycleThreshold = 4;
let settingsCache = null;

function durationForType(type) {
    if (!settingsCache) return 25 * 60;
    if (type === 'short_break') return Number(settingsCache.short_break) * 60;
    if (type === 'long_break') return Number(settingsCache.long_break) * 60;
    return Number(settingsCache.work_duration) * 60;
}

function setTimerStatus(message, isError = false) {
    if (!timerStatus) return;
    timerStatus.textContent = message || '';
    timerStatus.classList.toggle('error', Boolean(isError));
}

function inferNextSessionType(state) {
    const completed = Number(state.completed_pomodoros || 0);
    if (completed > 0 && completed % Math.max(1, cycleThreshold) === 0) {
        return 'long_break';
    }
    return completed > 0 ? 'short_break' : 'work';
}

function mmss(totalSeconds) {
    const safe = Math.max(0, Number(totalSeconds) || 0);
    const m = Math.floor(safe / 60).toString().padStart(2, '0');
    const s = Math.floor(safe % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
}

function updateTimerRing(state) {
    ringProgress.style.strokeDasharray = `${RING_CIRCUMFERENCE}`;

    if (!state.active) {
        ringProgress.style.strokeDashoffset = `${RING_CIRCUMFERENCE}`;
        ringProgress.style.opacity = '0';
        return;
    }

    const total = Math.max(1, Number(state.duration_seconds) || 1);
    const remaining = Math.max(0, Number(state.seconds_remaining) || 0);
    const progress = 1 - remaining / total;
    const dashOffset = RING_CIRCUMFERENCE * (1 - progress);

    ringProgress.style.strokeDashoffset = `${dashOffset}`;
    ringProgress.style.opacity = '1';
}

function updateTimeDisplay(state) {
    const seconds = state.active
        ? state.seconds_remaining
        : durationForType(state.next_session_type || inferNextSessionType(state));
    timeDisplay.textContent = mmss(seconds || 0);
}

function updateSessionLabel(state) {
    const type = state.active
        ? (state.session_type || 'work')
        : (state.next_session_type || inferNextSessionType(state));

    if (timerCard) {
        timerCard.classList.toggle('break', type !== 'work');
    }

    if (type === 'short_break') {
        sessionLabel.textContent = state.active ? 'SHORT BREAK' : 'NEXT: SHORT BREAK';
        return;
    }
    if (type === 'long_break') {
        sessionLabel.textContent = state.active ? 'LONG BREAK' : 'NEXT: LONG BREAK';
        return;
    }
    sessionLabel.textContent = state.active ? 'FOCUS' : 'NEXT: FOCUS';
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

    startBtn.disabled = active;
    pauseBtn.disabled = !active;
    skipBtn.disabled = !active;

    if (!active) {
        pauseBtn.textContent = 'Pause';
        const next = state.next_session_type || inferNextSessionType(state);
        startBtn.textContent = next === 'work' ? 'Start Focus' : 'Start Break';
    } else {
        pauseBtn.textContent = paused ? 'Resume' : 'Pause';
    }

    if (timerCard) {
        timerCard.classList.toggle('active', active && !paused);
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

async function loadCycleSettings() {
    const res = await fetch('/api/settings');
    if (!res.ok) {
        throw new Error(`Failed to load settings: ${res.status}`);
    }
    const settings = await res.json();
    settingsCache = settings;
    cycleThreshold = Math.max(1, Number(settings.long_break_after) || 4);
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
    const wasActive = Boolean(lastKnownState.active);
    lastKnownState = { ...lastKnownState, ...state };
    if (wasActive !== Boolean(lastKnownState.active)) {
        // A session just started or ended; refresh the dashboard widgets.
        loadDashboard().catch(() => {});
    }
    if (!lastKnownState.active) {
        lastKnownState.next_session_type = state.next_session_type || inferNextSessionType(lastKnownState);
    }
    updateTimerRing(lastKnownState);
    updateTimeDisplay(lastKnownState);
    updateSessionLabel(lastKnownState);
    updatePomodorodots(lastKnownState);
    updateButtonStates(lastKnownState);
    updateHeroStatus(lastKnownState);
}

startBtn.addEventListener('click', async () => {
    try {
        const body = { session_type: lastKnownState.next_session_type || inferNextSessionType(lastKnownState) };
        const data = await postJson('/session/start', body);
        if (data.state) {
            applyState(data.state);
        }
        setTimerStatus('');
    } catch (err) {
        setTimerStatus(err.message, true);
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
            setTimerStatus('');
        } else {
            const data = await postJson('/session/pause');
            if (data.state) {
                applyState(data.state);
            }
            setTimerStatus('');
        }
    } catch (err) {
        setTimerStatus(err.message, true);
        console.error(err);
    }
});

skipBtn.addEventListener('click', async () => {
    try {
        const data = await postJson('/session/skip');
        if (data.state) {
            applyState({ ...data.state, next_session_type: data.next_session_type });
        }
        setTimerStatus('');
    } catch (err) {
        setTimerStatus(err.message, true);
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

/* ---- Dashboard widgets ---- */

const clockTime = document.getElementById('clockTime');
const clockDate = document.getElementById('clockDate');
const greetingEl = document.getElementById('greeting');
const heroStatus = document.getElementById('heroStatus');

function greetingForHour(hour) {
    if (hour < 5) return 'Burning the midnight oil';
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    if (hour < 21) return 'Good evening';
    return 'Winding down';
}

function tickClock() {
    if (!clockTime) return;
    const now = new Date();
    const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    // Split off seconds so they render smaller, world-clock style.
    const parts = time.match(/^(\d{1,2}[:.]\d{2})[:.](\d{2})(.*)$/);
    if (parts) {
        clockTime.innerHTML = `${parts[1]}<small>:${parts[2]}</small>${parts[3] || ''}`;
    } else {
        clockTime.textContent = time;
    }
    clockDate.textContent = now.toLocaleDateString(undefined, {
        weekday: 'long', month: 'long', day: 'numeric',
    });
    if (greetingEl) {
        greetingEl.textContent = greetingForHour(now.getHours());
    }
}

function updateHeroStatus(state) {
    if (!heroStatus) return;
    let text = 'Ready for a focus session';
    if (state.active && state.paused) {
        text = 'Session paused — take your time';
    } else if (state.active && state.session_type === 'work') {
        text = 'In deep focus. Distractions silenced.';
    } else if (state.active) {
        text = 'On a break. Stretch, breathe, hydrate.';
    } else if (Number(state.completed_pomodoros) > 0) {
        text = `${state.completed_pomodoros} pomodoro${state.completed_pomodoros === 1 ? '' : 's'} down — keep the streak alive`;
    }
    if (heroStatus.textContent !== text) {
        heroStatus.textContent = text;
        heroStatus.classList.remove('swap');
        void heroStatus.offsetWidth; // restart animation
        heroStatus.classList.add('swap');
    }
}

/* Animated count-up for stat values */
function countUp(el, target, formatter) {
    const duration = 700;
    const start = performance.now();
    const from = Number(el.dataset.current || 0);
    const to = Number(target) || 0;
    el.dataset.current = String(to);

    if (from === to) {
        el.textContent = formatter(to);
        return;
    }

    function frame(now) {
        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3);
        el.textContent = formatter(Math.round(from + (to - from) * eased));
        if (t < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
}

function formatFocusMinutes(minutes) {
    const m = Math.max(0, Number(minutes) || 0);
    if (m < 60) return `${m}m`;
    const h = Math.floor(m / 60);
    const rem = m % 60;
    return rem ? `${h}h ${rem}m` : `${h}h`;
}

function renderWeekChart(week) {
    const host = document.getElementById('weekChart');
    if (!host) return;
    host.innerHTML = '';

    const max = Math.max(1, ...week.map((d) => d.count));
    week.forEach((d, i) => {
        const col = document.createElement('div');
        col.className = `mini-bar${d.count === 0 ? ' empty' : ''}${i === week.length - 1 ? ' today' : ''}`;
        col.title = `${d.date}: ${d.count} focus session${d.count === 1 ? '' : 's'}`;

        const value = document.createElement('span');
        value.className = 'bar-value';
        value.textContent = d.count || '';

        const bar = document.createElement('span');
        bar.className = 'bar';
        bar.style.height = d.count === 0 ? '4px' : `${Math.round((d.count / max) * 92) + 8}px`;
        bar.style.animationDelay = `${i * 60}ms`;

        const label = document.createElement('span');
        label.className = 'bar-label';
        label.textContent = d.day;

        col.append(value, bar, label);
        host.appendChild(col);
    });
}

function utilRow(name, pillText, pillClass) {
    const li = document.createElement('li');
    li.className = 'util-row';
    const left = document.createElement('span');
    left.className = 'util-name';
    left.textContent = name;
    const pill = document.createElement('span');
    pill.className = `pill ${pillClass}`;
    pill.textContent = pillText;
    li.append(left, pill);
    return li;
}

function renderUtilities(data) {
    const host = document.getElementById('utilList');
    if (!host) return;
    host.innerHTML = '';

    const s = data.settings || {};
    const p = data.permissions || {};
    const state = data.state || {};
    const focusing = Boolean(state.active) && state.session_type === 'work';

    const rows = [
        ['Site Blocking', s.block_sites, p.hosts_writable, focusing && s.block_sites],
        ['Do Not Disturb', s.enable_dnd, p.shortcuts, focusing && s.enable_dnd],
        ['Window Dimming', s.dim_windows, p.accessibility, focusing && s.dim_windows],
    ];

    rows.forEach(([name, enabled, permitted, live]) => {
        let pillText = 'Off';
        let pillClass = 'pill-off';
        if (live) {
            pillText = 'Active';
            pillClass = 'pill-live';
        } else if (enabled && permitted) {
            pillText = 'Ready';
            pillClass = 'pill-on';
        } else if (enabled && !permitted) {
            pillText = 'No Access';
            pillClass = 'pill-warn';
        }
        host.appendChild(utilRow(name, pillText, pillClass));
    });
}

function renderBlocklistWidget(data) {
    const enabled = (data.blocklist || {}).enabled || 0;
    const count = document.getElementById('blockCount');
    const total = document.getElementById('blockTotal');
    if (count) countUp(count, enabled, String);
    if (total) total.textContent = String(enabled);
}

async function renderBlockChips() {
    const chips = document.getElementById('blockChips');
    if (!chips) return;
    const res = await fetch('/api/blocklist');
    if (!res.ok) return;
    const entries = await res.json();
    chips.innerHTML = '';
    entries
        .filter((e) => e.enabled)
        .slice(0, 8)
        .forEach((e) => {
            const chip = document.createElement('span');
            chip.className = 'chip';
            chip.textContent = e.domain;
            chips.appendChild(chip);
        });
}

async function loadDashboard() {
    if (!document.getElementById('todayFocus')) return;
    const res = await fetch('/api/dashboard');
    if (!res.ok) throw new Error(`Dashboard load failed: ${res.status}`);
    const data = await res.json();

    countUp(document.getElementById('todayFocus'), data.today_focus_minutes, formatFocusMinutes);
    countUp(document.getElementById('todaySessions'), data.today_sessions, String);
    countUp(document.getElementById('streakDays'), data.streak_days, (v) => (v > 0 ? `${v}d` : '0'));

    // Daily goal ring (2h of completed focus).
    const goalRing = document.getElementById('goalRing');
    const goalPct = document.getElementById('goalPct');
    const goalSub = document.getElementById('goalSub');
    if (goalRing && goalPct) {
        const GOAL_MINUTES = 120;
        const minutes = Number(data.today_focus_minutes) || 0;
        const pct = Math.min(100, Math.round(minutes / GOAL_MINUTES * 100));
        const c = 2 * Math.PI * 52;
        goalRing.style.strokeDasharray = `${c}`;
        goalRing.style.strokeDashoffset = `${c * (1 - pct / 100)}`;
        goalRing.classList.toggle('done', pct >= 100);
        countUp(goalPct, pct, (v) => `${v}%`);
        if (goalSub) {
            goalSub.textContent = `${formatFocusMinutes(minutes)} of ${formatFocusMinutes(GOAL_MINUTES)} focused`;
        }
    }

    const weekTotal = document.getElementById('weekTotal');
    if (weekTotal) {
        const total = (data.week || []).reduce((sum, d) => sum + d.count, 0);
        weekTotal.textContent = `${total} session${total === 1 ? '' : 's'}`;
    }

    renderWeekChart(data.week || []);
    renderUtilities(data);
    renderBlocklistWidget(data);
}

if (clockTime) {
    tickClock();
    setInterval(tickClock, 1000);
}

checkPermissions();
loadDashboard().catch(() => {});
renderBlockChips().catch(() => {});
loadCycleSettings()
    .catch((err) => setTimerStatus(err.message, true))
    .finally(() => applyState(lastKnownState));
