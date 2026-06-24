/* ─── CrawlDB Dashboard — JavaScript Application ─── */

const API = '';
let ws = null;
let selectedDepth = 2;
let statsInterval = null;

// ─── Stats Polling ───
async function fetchStats() {
    try {
        const res = await fetch(`${API}/api/stats`);
        if (!res.ok) return;
        const data = await res.json();
        animateValue('statPagesCrawled', data.pages_crawled || 0);
        animateValue('statPagesIndexed', data.pages_indexed || 0);
        animateValue('statDomains', data.unique_domains || 0);
        animateValue('statQueueDepth', data.queue_depth || 0);
        animateValue('statDuplicates', data.duplicates_skipped || 0);
    } catch (e) { /* API not ready */ }
}

function animateValue(id, target) {
    const el = document.getElementById(id);
    const current = parseInt(el.textContent.replace(/,/g, '')) || 0;
    if (current === target) return;
    const diff = target - current;
    const steps = Math.min(Math.abs(diff), 20);
    const increment = diff / steps;
    let step = 0;
    const timer = setInterval(() => {
        step++;
        const val = step === steps ? target : Math.round(current + increment * step);
        el.textContent = val.toLocaleString();
        if (step >= steps) clearInterval(timer);
    }, 30);
}

// ─── WebSocket ───
function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws/live`);
    const statusEl = document.getElementById('connectionStatus');
    const dot = statusEl.querySelector('.status-dot');
    const text = statusEl.querySelector('.status-text');

    ws.onopen = () => {
        dot.className = 'status-dot connected';
        text.textContent = 'Connected';
    };
    ws.onclose = () => {
        dot.className = 'status-dot error';
        text.textContent = 'Disconnected';
        setTimeout(connectWebSocket, 3000);
    };
    ws.onerror = () => {
        dot.className = 'status-dot error';
        text.textContent = 'Error';
    };
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'heartbeat' || data.type === 'pong') return;
            addFeedItem(data);
            fetchStats();
        } catch (e) { /* ignore */ }
    };
}

// ─── Live Feed ───
function addFeedItem(event) {
    const feed = document.getElementById('liveFeed');
    const empty = feed.querySelector('.feed-empty');
    if (empty) empty.remove();

    const item = document.createElement('div');
    item.className = 'feed-item';
    const badgeClass = event.event_type || 'crawled';
    const time = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();

    item.innerHTML = `
        <span class="feed-badge ${badgeClass}">${badgeClass}</span>
        <div class="feed-content">
            <div class="feed-url">${escapeHtml(truncate(event.url || '', 80))}</div>
            ${event.detail ? `<div class="feed-detail">${escapeHtml(event.detail)}</div>` : ''}
        </div>
        <span class="feed-time">${time}</span>
    `;
    feed.insertBefore(item, feed.firstChild);

    // Cap feed items
    while (feed.children.length > 100) feed.removeChild(feed.lastChild);
}

// ─── Search ───
async function performSearch() {
    const query = document.getElementById('searchInput').value.trim();
    if (!query) return;

    const meta = document.getElementById('searchMeta');
    const results = document.getElementById('searchResults');
    meta.textContent = 'Searching...';
    results.innerHTML = '';

    try {
        const res = await fetch(`${API}/api/search?q=${encodeURIComponent(query)}&size=20`);
        if (!res.ok) { meta.textContent = 'Search failed'; return; }
        const data = await res.json();

        meta.textContent = `${data.total} results found (${data.took_ms}ms)`;

        if (data.results.length === 0) {
            results.innerHTML = '<div class="feed-empty"><p>No results found</p></div>';
            return;
        }

        data.results.forEach(r => {
            const item = document.createElement('div');
            item.className = 'search-result-item';
            item.onclick = () => window.open(r.url, '_blank');
            item.innerHTML = `
                <div class="result-title">${escapeHtml(r.title || 'Untitled')}</div>
                <div class="result-url">${escapeHtml(r.url)}</div>
                ${r.snippet ? `<div class="result-snippet">${r.snippet}</div>` : ''}
                <div class="result-meta">
                    <span>${escapeHtml(r.domain || '')}</span>
                    <span>Score: ${r.score?.toFixed(2) || '—'}</span>
                </div>
            `;
            results.appendChild(item);
        });
    } catch (e) {
        meta.textContent = 'Search error: ' + e.message;
    }
}

// ─── Start Crawl ───
async function startCrawl() {
    const urlInput = document.getElementById('seedUrl');
    const btn = document.getElementById('startCrawlBtn');
    const status = document.getElementById('crawlStatus');
    const url = urlInput.value.trim();
    if (!url) return;

    btn.disabled = true;
    status.textContent = 'Submitting...';
    status.style.color = 'var(--amber)';

    try {
        const res = await fetch(`${API}/api/crawl`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls: [url], max_depth: selectedDepth }),
        });
        const data = await res.json();
        status.textContent = `✓ ${data.urls_submitted} URL(s) queued (depth: ${selectedDepth})`;
        status.style.color = 'var(--green)';
        fetchStats();
    } catch (e) {
        status.textContent = '✗ Error: ' + e.message;
        status.style.color = 'var(--red)';
    } finally {
        btn.disabled = false;
    }
}

// ─── Load Recent Pages ───
async function loadPages() {
    try {
        const res = await fetch(`${API}/api/pages?size=30`);
        if (!res.ok) return;
        const data = await res.json();
        const tbody = document.getElementById('pagesTableBody');

        if (!data.pages || data.pages.length === 0) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="4">No pages crawled yet</td></tr>';
            return;
        }

        tbody.innerHTML = data.pages.map(p => `
            <tr>
                <td>
                    <span class="page-title">${escapeHtml(p.title || 'Untitled')}</span>
                    <span class="page-url">${escapeHtml(p.url)}</span>
                </td>
                <td style="color:var(--text-secondary);font-size:0.75rem">${escapeHtml(p.domain || '')}</td>
                <td><span class="status-badge ${p.status_code === 200 ? 'ok' : 'err'}">${p.status_code}</span></td>
                <td style="color:var(--text-muted);font-size:0.7rem;font-family:var(--font-mono)">${p.fetch_time_ms?.toFixed(0) || '—'}ms</td>
            </tr>
        `).join('');
    } catch (e) { /* API not ready */ }
}

// ─── Utilities ───
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
function truncate(str, len) { return str.length > len ? str.slice(0, len) + '...' : str; }

// ─── Event Listeners ───
document.addEventListener('DOMContentLoaded', () => {
    // Initial load
    fetchStats();
    loadPages();
    connectWebSocket();
    statsInterval = setInterval(fetchStats, 5000);

    // Search
    document.getElementById('searchBtn').addEventListener('click', performSearch);
    document.getElementById('searchInput').addEventListener('keydown', e => { if (e.key === 'Enter') performSearch(); });

    // Debounced search
    let searchTimeout;
    document.getElementById('searchInput').addEventListener('input', () => {
        clearTimeout(searchTimeout);
        const q = document.getElementById('searchInput').value.trim();
        if (q.length >= 3) searchTimeout = setTimeout(performSearch, 400);
    });

    // Crawl
    document.getElementById('startCrawlBtn').addEventListener('click', startCrawl);
    document.querySelectorAll('.depth-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.depth-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedDepth = parseInt(btn.dataset.depth);
        });
    });

    // Clear feed
    document.getElementById('clearFeed').addEventListener('click', () => {
        document.getElementById('liveFeed').innerHTML = '<div class="feed-empty"><p>Feed cleared</p></div>';
    });

    // Refresh pages
    document.getElementById('refreshPages').addEventListener('click', loadPages);
});
