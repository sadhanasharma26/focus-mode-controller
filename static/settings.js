function normalizeDomain(raw) {
    let value = (raw || '').trim().toLowerCase();
    value = value.replace(/^https?:\/\//, '');
    value = value.split('/')[0];
    value = value.replace(/^www\./, '');
    return value;
}

function boolIcon(value) {
    return value ? 'OK' : 'WARN';
}

async function fetchJson(url, options = {}) {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        throw new Error(data.error || `Request failed: ${res.status}`);
    }
    return data;
}

function bindOpacityPreview() {
    const slider = document.getElementById('dimOpacity');
    const label = document.getElementById('dimOpacityValue');
    slider.addEventListener('input', () => {
        label.textContent = `${slider.value}%`;
    });
}

function readSettingsForm() {
    return {
        work_duration: Number(document.getElementById('workDuration').value),
        short_break: Number(document.getElementById('shortBreak').value),
        long_break: Number(document.getElementById('longBreak').value),
        long_break_after: Number(document.getElementById('longBreakAfter').value),
        block_sites: document.getElementById('blockSites').checked,
        enable_dnd: document.getElementById('enableDnd').checked,
        dim_windows: document.getElementById('dimWindows').checked,
        dim_opacity: Number(document.getElementById('dimOpacity').value) / 100,
    };
}

function writeSettingsForm(settings) {
    document.getElementById('workDuration').value = settings.work_duration;
    document.getElementById('shortBreak').value = settings.short_break;
    document.getElementById('longBreak').value = settings.long_break;
    document.getElementById('longBreakAfter').value = settings.long_break_after;

    document.getElementById('blockSites').checked = Boolean(settings.block_sites);
    document.getElementById('enableDnd').checked = Boolean(settings.enable_dnd);
    document.getElementById('dimWindows').checked = Boolean(settings.dim_windows);

    const percent = Math.round(Number(settings.dim_opacity || 0) * 100);
    document.getElementById('dimOpacity').value = percent;
    document.getElementById('dimOpacityValue').textContent = `${percent}%`;
}

function setSaveStatus(text, isError = false) {
    const status = document.getElementById('saveStatus');
    status.textContent = text;
    status.style.color = isError ? '#f08a8a' : 'var(--muted)';
}

async function loadSettings() {
    const settings = await fetchJson('/api/settings');
    writeSettingsForm(settings);
}

function blocklistRow(entry) {
    const row = document.createElement('div');
    row.className = 'blocklist-row';

    const domain = document.createElement('span');
    domain.textContent = entry.domain;

    const actions = document.createElement('div');
    actions.className = 'row-actions';

    const toggle = document.createElement('button');
    toggle.className = 'btn';
    toggle.textContent = entry.enabled ? 'Disable' : 'Enable';
    toggle.addEventListener('click', async () => {
        try {
            await fetchJson(`/api/blocklist/${entry.id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: !entry.enabled }),
            });
            await loadBlocklist();
        } catch (err) {
            setSaveStatus(err.message, true);
        }
    });

    const del = document.createElement('button');
    del.className = 'btn';
    del.textContent = 'Delete';
    del.addEventListener('click', async () => {
        try {
            await fetchJson(`/api/blocklist/${entry.id}`, { method: 'DELETE' });
            await loadBlocklist();
        } catch (err) {
            setSaveStatus(err.message, true);
        }
    });

    actions.append(toggle, del);
    row.append(domain, actions);
    return row;
}

async function loadBlocklist() {
    const rowsHost = document.getElementById('blocklistRows');
    rowsHost.innerHTML = '';
    const entries = await fetchJson('/api/blocklist');

    if (!entries.length) {
        const empty = document.createElement('p');
        empty.className = 'muted-text';
        empty.textContent = 'No domains added.';
        rowsHost.appendChild(empty);
        return;
    }

    entries.forEach((entry) => rowsHost.appendChild(blocklistRow(entry)));
}

async function loadPermissions() {
    const host = document.getElementById('permissionStatus');
    host.innerHTML = '';
    const p = await fetchJson('/api/permissions');

    const items = [
        ['Hosts Writable', p.hosts_writable],
        ['Accessibility', p.accessibility],
        ['Shortcuts CLI', p.shortcuts],
    ];

    items.forEach(([label, value]) => {
        const row = document.createElement('div');
        row.className = 'permission-row';
        row.innerHTML = `<span>${label}</span><strong class="perm-${value ? 'ok' : 'warn'}">${boolIcon(value)}</strong>`;
        host.appendChild(row);
    });
}

function bindActions() {
    document.getElementById('saveSettingsBtn').addEventListener('click', async () => {
        try {
            setSaveStatus('Saving...');
            const payload = readSettingsForm();
            await fetchJson('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            setSaveStatus('Settings saved.');
        } catch (err) {
            setSaveStatus(err.message, true);
        }
    });

    document.getElementById('addDomainBtn').addEventListener('click', async () => {
        try {
            const input = document.getElementById('domainInput');
            const domain = normalizeDomain(input.value);
            if (!domain) {
                setSaveStatus('Enter a valid domain.', true);
                return;
            }
            await fetchJson('/api/blocklist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ domain }),
            });
            input.value = '';
            setSaveStatus('Domain added.');
            await loadBlocklist();
        } catch (err) {
            setSaveStatus(err.message, true);
        }
    });
}

async function initSettingsPage() {
    bindOpacityPreview();
    bindActions();
    await loadSettings();
    await loadBlocklist();
    await loadPermissions();
}

initSettingsPage().catch((err) => setSaveStatus(err.message, true));
