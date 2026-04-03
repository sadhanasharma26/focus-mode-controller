function formatType(sessionType) {
    if (sessionType === 'short_break') return 'Short Break';
    if (sessionType === 'long_break') return 'Long Break';
    return 'Focus';
}

function dateKey(date) {
    return date.toISOString().slice(0, 10);
}

function localDayLabel(date) {
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function buildLastNDays(n) {
    const days = [];
    const now = new Date();
    for (let i = n - 1; i >= 0; i -= 1) {
        const d = new Date(now);
        d.setHours(0, 0, 0, 0);
        d.setDate(d.getDate() - i);
        days.push(d);
    }
    return days;
}

function renderStats(history) {
    const workSessions = history.filter((row) => row.session_type === 'work' && row.completed);
    const totalFocusMinutes = workSessions.reduce((sum, row) => sum + Number(row.duration_minutes || 0), 0);
    const totalSessions = history.length;
    const representedDays = new Set(
        history
            .filter((row) => row.started_at)
            .map((row) => row.started_at.slice(0, 10)),
    ).size;
    const avgDivisor = Math.max(1, Math.min(14, representedDays));
    const avgPerDay = (totalSessions / avgDivisor).toFixed(1);

    const dayCounts = {};
    history.forEach((row) => {
        if (!row.started_at) return;
        const key = row.started_at.slice(0, 10);
        dayCounts[key] = (dayCounts[key] || 0) + 1;
    });

    let bestDay = '-';
    let maxCount = 0;
    Object.entries(dayCounts).forEach(([key, count]) => {
        if (count > maxCount) {
            maxCount = count;
            bestDay = `${key} (${count})`;
        }
    });

    document.getElementById('statFocusTime').textContent = `${totalFocusMinutes}m`;
    document.getElementById('statTotalSessions').textContent = String(totalSessions);
    document.getElementById('statAvgPerDay').textContent = avgPerDay;
    document.getElementById('statBestDay').textContent = bestDay;
}

function renderChart(history) {
    const days = buildLastNDays(14);
    const labelKeys = days.map(dateKey);
    const labels = days.map(localDayLabel);
    const counts = new Array(14).fill(0);

    history.forEach((row) => {
        if (!row.started_at || !row.completed) return;
        const key = row.started_at.slice(0, 10);
        const idx = labelKeys.indexOf(key);
        if (idx !== -1) {
            counts[idx] += 1;
        }
    });

    const ctx = document.getElementById('historyChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Completed Sessions',
                data: counts,
                backgroundColor: '#e06c4e',
                borderRadius: 6,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { color: '#aaa', precision: 0 },
                    grid: { color: '#2a2a2a' },
                },
                x: {
                    ticks: { color: '#aaa' },
                    grid: { display: false },
                },
            },
        },
    });
}

function renderTable(history) {
    const tbody = document.getElementById('historyRows');
    tbody.innerHTML = '';

    if (!history.length) {
        const tr = document.createElement('tr');
        tr.innerHTML = '<td colspan="4" class="muted-text">No sessions yet.</td>';
        tbody.appendChild(tr);
        return;
    }

    history.forEach((row) => {
        const tr = document.createElement('tr');
        const when = row.started_at ? new Date(row.started_at).toLocaleString() : '-';
        const completed = row.completed ? 'YES' : 'NO';
        tr.innerHTML = `
            <td>${when}</td>
            <td>${formatType(row.session_type)}</td>
            <td>${row.duration_minutes}m</td>
            <td>${completed}</td>
        `;
        tbody.appendChild(tr);
    });
}

async function initHistoryPage() {
    const res = await fetch('/api/history');
    const history = await res.json();
    renderStats(history);
    renderChart(history);
    renderTable(history);
}

initHistoryPage().catch((err) => {
    const tbody = document.getElementById('historyRows');
    tbody.innerHTML = `<tr><td colspan="4" class="muted-text">Failed to load history: ${err.message}</td></tr>`;
});
