/**
 * Pitch Visualizer — Frontend Script
 * Handles:
 *  - Style card selection
 *  - Form submission (streaming SSE or batch)
 *  - Live panel rendering via Server-Sent Events
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── Style card selection ──
    const styleCards = document.querySelectorAll('.style-card');
    styleCards.forEach(card => {
        card.addEventListener('click', () => {
            styleCards.forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
            card.querySelector('input').checked = true;
        });
    });

    // ── Form submission ──
    const form = document.getElementById('visualizer-form');
    const submitBtn = document.getElementById('submit-btn');
    const storyboardArea = document.getElementById('storyboard-area');
    const panelsContainer = document.getElementById('panels-container');
    const statusMsg = document.getElementById('status-msg');
    const progressBar = document.getElementById('progress-bar');
    const completeActions = document.getElementById('complete-actions');

    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const formData = new FormData(form);
        const mode = formData.get('mode') || 'stream';

        // Show storyboard area
        storyboardArea.classList.remove('hidden');
        panelsContainer.innerHTML = '';
        completeActions && completeActions.classList.add('hidden');
        progressBar.style.width = '5%';
        submitBtn.disabled = true;
        submitBtn.querySelector('.btn-text').textContent = 'Generating…';

        // Scroll to storyboard
        storyboardArea.scrollIntoView({ behavior: 'smooth', block: 'start' });

        if (mode === 'stream') {
            await runStreamMode(formData);
        } else {
            await runBatchMode(formData);
        }
    });

    // ── STREAMING MODE ──
    async function runStreamMode(formData) {
        updateStatus('🔍 Segmenting narrative…');
        progressBar.style.width = '10%';

        try {
            const response = await fetch('/generate-stream', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) throw new Error(`Server error: ${response.status}`);

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let totalPanels = 0;
            let panelsReceived = 0;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const event = JSON.parse(line.slice(6));
                        handleSSEEvent(event, () => totalPanels, (n) => totalPanels = n,
                                        () => panelsReceived, (n) => panelsReceived = n);
                    } catch (_) {}
                }
            }
        } catch (err) {
            updateStatus(`❌ Error: ${err.message}`);
        } finally {
            resetButton();
        }
    }

    function handleSSEEvent(event, getTotal, setTotal, getReceived, setReceived) {
        switch (event.type) {
            case 'scenes_ready':
                updateStatus(`✂️ Segmented into ${event.count} scenes`);
                progressBar.style.width = '20%';
                // Pre-create skeleton cards
                for (let i = 0; i < event.count; i++) {
                    panelsContainer.appendChild(createSkeletonPanel(i + 1));
                }
                break;

            case 'prompts_ready':
                updateStatus(`✨ Engineered ${event.count} visual prompts — generating images…`);
                progressBar.style.width = '35%';
                setTotal(event.count);
                break;

            case 'panel': {
                setReceived(getReceived() + 1);
                const pct = 35 + Math.round((getReceived() / (getTotal() || event.total)) * 60);
                progressBar.style.width = `${pct}%`;
                updateStatus(`🎨 Generated panel ${event.index} of ${event.total}…`);

                // Replace skeleton with real panel
                const skeleton = document.getElementById(`skeleton-${event.index}`);
                const realPanel = createRealPanel(event);
                if (skeleton) {
                    skeleton.replaceWith(realPanel);
                } else {
                    panelsContainer.appendChild(realPanel);
                }
                break;
            }

            case 'complete':
                progressBar.style.width = '100%';
                updateStatus('✅ Storyboard complete!');
                completeActions && completeActions.classList.remove('hidden');
                resetButton();
                break;
        }
    }

    // ── BATCH MODE ──
    async function runBatchMode(formData) {
        updateStatus('⚙️ Generating all panels… (this may take 30–60 seconds)');
        progressBar.style.width = '15%';

        // Show spinner
        const spinner = document.createElement('div');
        spinner.className = 'batch-spinner';
        spinner.innerHTML = '<div class="spinner"></div>';
        panelsContainer.appendChild(spinner);

        try {
            // POST to /generate which returns full storyboard HTML
            const resp = await fetch('/generate', { method: 'POST', body: formData });
            progressBar.style.width = '90%';

            if (!resp.ok) throw new Error(`Server error ${resp.status}`);
            const html = await resp.text();

            // Extract panels from returned HTML and render them
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newPanels = doc.querySelectorAll('.panel-card');
            panelsContainer.innerHTML = '';
            newPanels.forEach(p => panelsContainer.appendChild(p));

            progressBar.style.width = '100%';
            updateStatus('✅ Storyboard complete!');
            completeActions && completeActions.classList.remove('hidden');
        } catch (err) {
            updateStatus(`❌ Error: ${err.message}`);
        } finally {
            resetButton();
        }
    }

    // ── Helpers ──
    function createSkeletonPanel(index) {
        const card = document.createElement('div');
        card.className = 'panel-card';
        card.id = `skeleton-${index}`;
        card.innerHTML = `
            <div class="panel-header">
                <span class="panel-number">Panel ${index}</span>
                <span style="font-size:0.75rem;color:var(--text-muted)">Generating…</span>
            </div>
            <div class="panel-image-wrap"><div class="panel-skeleton"></div></div>
            <div class="panel-caption">
                <p class="caption-text" style="color:var(--text-muted)">⏳ Awaiting image generation…</p>
            </div>
        `;
        return card;
    }

    function createRealPanel(event) {
        const card = document.createElement('div');
        card.className = 'panel-card';
        const imgHtml = event.image_url
            ? `<img src="${event.image_url}" alt="Scene ${event.index}" class="panel-image" loading="lazy" />`
            : `<div class="panel-placeholder"><span>🖼️</span><p>Image unavailable</p></div>`;
        card.innerHTML = `
            <div class="panel-header">
                <span class="panel-number">Panel ${event.index}</span>
            </div>
            <div class="panel-image-wrap">${imgHtml}</div>
            <div class="panel-caption">
                <p class="caption-text">${escapeHtml(event.scene_text)}</p>
            </div>
            <details class="prompt-details">
                <summary>View engineered prompt</summary>
                <p class="prompt-text">${escapeHtml(event.engineered_prompt)}</p>
            </details>
        `;
        return card;
    }

    function updateStatus(msg) {
        if (statusMsg) statusMsg.textContent = msg;
    }

    function resetButton() {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.querySelector('.btn-text').textContent = 'Generate Storyboard';
        }
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
});