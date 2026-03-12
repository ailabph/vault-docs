// vault-docs — Air-Gapped Document Analyzer
// Frontend application logic

(function () {
    'use strict';

    // ── State ─────────────────────────────────────────────────────
    let state = {
        currentState: 'upload',
        sessionId: null
    };

    // ── DOM References ────────────────────────────────────────────
    const stateUpload     = document.getElementById('state-upload');
    const stateProcessing = document.getElementById('state-processing');
    const stateResults    = document.getElementById('state-results');
    const dropZone        = document.getElementById('drop-zone');
    const fileInput       = document.getElementById('file-input');
    const uploadError     = document.getElementById('upload-error');
    const chatHistory     = document.getElementById('chat-history');
    const questionInput   = document.getElementById('question');
    const sendBtn         = document.getElementById('send-btn');
    const resetBtn        = document.getElementById('reset-btn');

    

    // ── Status Bar — Real-time GPU & Model ──────────────────────
    const statusDot       = document.getElementById('status-dot');
    const statusText      = document.getElementById('status-text');
    const gpuInstances    = document.getElementById('gpu-instances');
    const activeModelEl   = document.getElementById('active-model');
    const STATUS_INTERVAL = 5000;

    function gpuBarClass(pct) {
        if (pct >= 80) return 'high';
        if (pct >= 40) return 'medium';
        return 'low';
    }

    function renderGpuChips(models) {
        if (!models || models.length === 0) {
            gpuInstances.innerHTML = '<span style="color:var(--text-muted);font-size:0.75rem;">No models loaded</span>';
            return;
        }
        gpuInstances.innerHTML = models.map(function (m) {
            var pct = m.gpu_percent || 0;
            var details = m.details || {};
            var paramSize = details.parameter_size || '';
            var quant = details.quantization || '';
            var label = paramSize ? (paramSize + (quant ? ' ' + quant : '')) : m.size;
            return '<div class="gpu-chip">' +
                '<span class="chip-icon">⬢</span>' +
                '<span class="chip-label">GPU</span>' +
                '<span>' + m.name + '</span>' +
                '<div class="gpu-bar-container" title="' + pct + '% VRAM">' +
                    '<div class="gpu-bar-fill ' + gpuBarClass(pct) + '" style="width:' + pct + '%"></div>' +
                '</div>' +
                '<span style="color:var(--text-muted)">' + pct + '% · ' + m.size_vram + '</span>' +
            '</div>';
        }).join('');
    }

    async function pollStatus() {
        try {
            var resp = await fetch('/api/status');
            if (!resp.ok) throw new Error('status ' + resp.status);
            var data = await resp.json();

            // Connection status
            if (data.ollama === 'reachable') {
                statusDot.className = 'status-dot online';
                statusText.textContent = 'Ollama Online';
            } else {
                statusDot.className = 'status-dot offline';
                statusText.textContent = 'Ollama Offline';
            }

            // GPU instances
            renderGpuChips(data.running_models);

            // GPU label
            var gpuLabel = data.gpu_label || '';
            var gpuLabelEl = document.getElementById('gpu-label');
            if (gpuLabelEl) gpuLabelEl.textContent = gpuLabel;

            // Active model in footer + status bar
            var modelName = data.configured_model || '—';
            if (data.running_models && data.running_models.length > 0) {
                modelName = data.running_models[0].name;
            }
            activeModelEl.textContent = '⚡ ' + modelName;

            var footerModelEl = document.getElementById('model-name');
            if (footerModelEl) footerModelEl.textContent = modelName;

        } catch (e) {
            statusDot.className = 'status-dot offline';
            statusText.textContent = 'Server Unreachable';
            gpuInstances.innerHTML = '';
            activeModelEl.textContent = '—';
        }
    }

    // Initial poll + interval
    pollStatus();
    setInterval(pollStatus, STATUS_INTERVAL);

    // ── Allowed extensions and size ───────────────────────────────
    const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt'];

    function getMaxUploadMB() {
        const attr = dropZone.getAttribute('data-max-mb');
        return attr ? parseInt(attr, 10) : 50;
    }

    // ── State Transitions ─────────────────────────────────────────

    function showUpload() {
        stateUpload.classList.remove('hidden');
        stateProcessing.classList.add('hidden');
        stateResults.classList.add('hidden');
        uploadError.classList.add('hidden');
        uploadError.textContent = '';
        state.currentState = 'upload';
    }

    function showProcessing() {
        stateUpload.classList.add('hidden');
        stateProcessing.classList.remove('hidden');
        stateResults.classList.add('hidden');
        uploadError.classList.add('hidden');
        uploadError.textContent = '';
        state.currentState = 'processing';
    }

    function showResults(data) {
        stateUpload.classList.add('hidden');
        stateProcessing.classList.add('hidden');
        stateResults.classList.remove('hidden');
        uploadError.classList.add('hidden');
        uploadError.textContent = '';
        state.currentState = 'results';

        // Render summary
        document.getElementById('summary').textContent = data.summary || '';

        // Render key points
        var keyPointsList = document.getElementById('key-points');
        keyPointsList.innerHTML = '';
        if (data.key_points && Array.isArray(data.key_points)) {
            data.key_points.forEach(function (point) {
                var li = document.createElement('li');
                li.textContent = point;
                keyPointsList.appendChild(li);
            });
        }

        // Focus the question input
        if (questionInput) {
            questionInput.focus();
        }
    }

    // ── File Validation ───────────────────────────────────────────

    function validateFile(file) {
        if (!file) {
            return { valid: false, error: 'No file selected.' };
        }

        // Check extension
        var fileName = file.name.toLowerCase();
        var ext = fileName.substring(fileName.lastIndexOf('.'));
        if (ALLOWED_EXTENSIONS.indexOf(ext) === -1) {
            return {
                valid: false,
                error: 'Unsupported file type. Please upload a PDF, DOCX, or TXT file.'
            };
        }

        // Check size
        var maxMB = getMaxUploadMB();
        var maxBytes = maxMB * 1024 * 1024;
        if (file.size > maxBytes) {
            return {
                valid: false,
                error: 'File exceeds the ' + maxMB + ' MB size limit.'
            };
        }

        return { valid: true };
    }

    // ── Display Error ─────────────────────────────────────────────

    function showError(message) {
        uploadError.textContent = message;
        uploadError.classList.remove('hidden');
    }

    // ── Handle File Selection ─────────────────────────────────────

    function handleFile(file) {
        var result = validateFile(file);
        if (!result.valid) {
            showError(result.error);
            return;
        }

        // Valid file — transition to processing and analyze
        showProcessing();
        analyzeDocument(file);
    }

    // ── Analyze Document ─────────────────────────────────────────

    async function analyzeDocument(file) {
        try {
            var formData = new FormData();
            formData.append('file', file);

            var response = await fetch('/api/analyze', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                var errorMsg;
                switch (response.status) {
                    case 400:
                        errorMsg = 'Unsupported or empty file. Please try a different document.';
                        break;
                    case 413:
                        errorMsg = 'File exceeds the 50 MB size limit.';
                        break;
                    case 503:
                        errorMsg = 'Inference service unavailable. Please try again shortly.';
                        break;
                    default:
                        errorMsg = 'Unexpected error. Please try again.';
                }
                showUpload();
                showError(errorMsg);
                return;
            }

            var data = await response.json();
            state.sessionId = data.session_id;
            showResults({ summary: data.summary, key_points: data.key_points });

        } catch (err) {
            showUpload();
            showError('Could not reach the server. Check your connection.');
        }
    }

    // ── Chat ─────────────────────────────────────────────────────

    function appendMessage(role, content) {
        var div = document.createElement('div');
        div.className = 'message message-' + role;
        div.textContent = content;
        chatHistory.appendChild(div);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    // ── Streaming state for think/answer routing ────────────────
    var streamState = {
        thinking: false,
        thinkingEl: null,
        thinkingContentEl: null,
        answerEl: null,
        buffer: ''
    };

    function resetStreamState() {
        streamState.thinking = false;
        streamState.thinkingEl = null;
        streamState.thinkingContentEl = null;
        streamState.answerEl = null;
        streamState.buffer = '';
    }

    function ensureThinkingBlock() {
        if (streamState.thinkingEl) return;
        var block = document.createElement('div');
        block.className = 'thinking-block';

        var label = document.createElement('div');
        label.className = 'thinking-label';
        label.textContent = '\u{1F9E0} Thinking\u2026';
        block.appendChild(label);

        var content = document.createElement('div');
        content.className = 'thinking-content';
        block.appendChild(content);

        chatHistory.appendChild(block);
        streamState.thinkingEl = block;
        streamState.thinkingContentEl = content;
    }

    function ensureAnswerBubble() {
        if (streamState.answerEl) return;
        var div = document.createElement('div');
        div.className = 'message message-assistant';
        chatHistory.appendChild(div);
        streamState.answerEl = div;
    }

    /**
     * Process a streamed token, routing text to thinking-block or answer-bubble.
     *
     * Handles <think>/<\/think> tags that may be split across arbitrary chunk
     * boundaries by buffering potential partial tags and only emitting text
     * once we know it's safe.
     */
    function appendStreamToken(token, done) {
        // Append new token to the pending buffer
        streamState.buffer += token;

        // Drain as much safe text from the buffer as possible
        drainBuffer();

        // --- Finalize on done ---
        if (done) {
            // Flush whatever remains in the buffer as-is (incomplete tag = literal text)
            flushBufferRemainder();
            if (!streamState.answerEl) {
                ensureAnswerBubble();
            }
            resetStreamState();
        }

        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    /**
     * Drain the buffer, emitting safe text and handling complete tags.
     * Leaves any potential partial-tag suffix in the buffer for the next token.
     */
    function drainBuffer() {
        // Keep looping while we can make progress
        while (streamState.buffer.length > 0) {
            if (streamState.thinking) {
                // Inside <think> — look for </think>
                var closeIdx = streamState.buffer.indexOf('</think>');
                if (closeIdx !== -1) {
                    // Emit text before the tag into thinking block
                    var before = streamState.buffer.substring(0, closeIdx);
                    if (before) {
                        ensureThinkingBlock();
                        streamState.thinkingContentEl.textContent += before;
                    }
                    // Consume the tag
                    streamState.buffer = streamState.buffer.substring(closeIdx + 8);
                    streamState.thinking = false;
                    collapseThinkingBlock();
                    ensureAnswerBubble();
                    continue; // keep draining — there may be answer text after
                }
                // No complete </think> yet — check for partial tag at end
                var safeLen = safeEmitLength(streamState.buffer, '</think>');
                if (safeLen > 0) {
                    ensureThinkingBlock();
                    streamState.thinkingContentEl.textContent += streamState.buffer.substring(0, safeLen);
                    streamState.buffer = streamState.buffer.substring(safeLen);
                }
                break; // rest of buffer might be partial tag — wait for more
            } else {
                // Outside <think> — look for <think>
                var openIdx = streamState.buffer.indexOf('<think>');
                if (openIdx !== -1) {
                    // Emit text before the tag into answer bubble
                    var beforeOpen = streamState.buffer.substring(0, openIdx);
                    if (beforeOpen) {
                        ensureAnswerBubble();
                        streamState.answerEl.textContent += beforeOpen;
                    }
                    // Consume the tag
                    streamState.buffer = streamState.buffer.substring(openIdx + 7);
                    streamState.thinking = true;
                    ensureThinkingBlock();
                    continue; // keep draining — thinking text follows
                }
                // No complete <think> yet — check for partial tag at end
                var safeAnswerLen = safeEmitLength(streamState.buffer, '<think>');
                if (safeAnswerLen > 0) {
                    ensureAnswerBubble();
                    streamState.answerEl.textContent += streamState.buffer.substring(0, safeAnswerLen);
                    streamState.buffer = streamState.buffer.substring(safeAnswerLen);
                }
                break; // rest might be partial — wait
            }
        }
    }

    /**
     * Return how many leading characters of `buf` are safe to emit, given that
     * `tag` might be arriving split across chunks. Any suffix of `buf` that
     * matches a prefix of `tag` must be held back.
     */
    function safeEmitLength(buf, tag) {
        var holdBack = 0;
        // Check increasingly long suffixes of buf against prefixes of tag
        var maxCheck = Math.min(buf.length, tag.length - 1);
        for (var i = 1; i <= maxCheck; i++) {
            if (buf.substring(buf.length - i) === tag.substring(0, i)) {
                holdBack = i;
            }
        }
        return buf.length - holdBack;
    }

    /**
     * Flush any remaining buffer text as literal output (called on stream end).
     */
    function flushBufferRemainder() {
        if (!streamState.buffer) return;
        if (streamState.thinking) {
            ensureThinkingBlock();
            streamState.thinkingContentEl.textContent += streamState.buffer;
            collapseThinkingBlock();
        } else {
            ensureAnswerBubble();
            streamState.answerEl.textContent += streamState.buffer;
        }
        streamState.buffer = '';
    }

    function collapseThinkingBlock() {
        if (streamState.thinkingEl) {
            streamState.thinkingEl.classList.add('collapsed');
            var label = streamState.thinkingEl.querySelector('.thinking-label');
            if (label) {
                label.textContent = '\u{1F9E0} Thinking (click to expand)';
            }
        }
    }

    async function sendChatMessage() {
        var question = questionInput.value.trim();
        if (!question) {
            return;
        }

        // Show user message and clear input
        appendMessage('user', question);
        questionInput.value = '';

        // Disable input during streaming
        questionInput.disabled = true;
        sendBtn.disabled = true;

        try {
            var response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: state.sessionId,
                    question: question
                })
            });

            // Non-OK status → handle as before (JSON error)
            if (!response.ok) {
                if (response.status === 404) {
                    appendMessage('error', 'Session expired \u2014 please re-upload your document.');
                } else {
                    appendMessage('error', 'Inference service unavailable. Please try again.');
                }
                return;
            }

            // OK → read SSE stream
            var reader = response.body.getReader();
            var decoder = new TextDecoder();
            var sseBuffer = '';

            while (true) {
                var result = await reader.read();
                if (result.done) break;

                sseBuffer += decoder.decode(result.value, { stream: true });

                // Split on double-newline (SSE event boundary)
                var events = sseBuffer.split('\n\n');
                // Last element may be incomplete — keep it in buffer
                sseBuffer = events.pop();

                for (var i = 0; i < events.length; i++) {
                    var eventText = events[i].trim();
                    if (!eventText) continue;

                    // Strip "data: " prefix
                    if (eventText.indexOf('data: ') === 0) {
                        eventText = eventText.substring(6);
                    }

                    var parsed;
                    try {
                        parsed = JSON.parse(eventText);
                    } catch (e) {
                        continue; // skip unparseable lines
                    }

                    if (parsed.error) {
                        appendMessage('error', parsed.error);
                        resetStreamState();
                        return;
                    }

                    if ('token' in parsed) {
                        appendStreamToken(parsed.token, parsed.done);
                        if (parsed.done) return;
                    }
                }
            }
        } catch (err) {
            appendMessage('error', 'Inference service unavailable. Please try again.');
            resetStreamState();
        } finally {
            questionInput.disabled = false;
            sendBtn.disabled = false;
            questionInput.focus();
        }
    }

    // ── Thinking block expand/collapse on click ─────────────────
    chatHistory.addEventListener('click', function (e) {
        var block = e.target.closest('.thinking-block');
        if (block && block.classList.contains('collapsed')) {
            block.classList.remove('collapsed');
            var label = block.querySelector('.thinking-label');
            if (label) {
                label.textContent = '\u{1F9E0} Thinking (click to collapse)';
            }
        } else if (block && !block.classList.contains('collapsed')) {
            // Allow re-collapsing too
            block.classList.add('collapsed');
            var label2 = block.querySelector('.thinking-label');
            if (label2) {
                label2.textContent = '\u{1F9E0} Thinking (click to expand)';
            }
        }
    });

    // ── Reset ────────────────────────────────────────────────────

    function resetAll() {
        state.sessionId = null;
        chatHistory.innerHTML = '';
        document.getElementById('key-points').innerHTML = '';
        document.getElementById('summary').textContent = '';
        fileInput.value = '';
        resetStreamState();
        showUpload();
    }

    // ── Event Bindings: Chat ─────────────────────────────────────

    sendBtn.addEventListener('click', function () {
        sendChatMessage();
    });

    questionInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });

    resetBtn.addEventListener('click', function () {
        resetAll();
    });

    // ── Event Bindings: Drag-and-Drop ────────────────────────────

    dropZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', function (e) {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', function (e) {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('drag-over');

        var files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    // ── Event Bindings: Click-to-Browse ──────────────────────────

    dropZone.addEventListener('click', function () {
        fileInput.click();
    });

    fileInput.addEventListener('change', function (e) {
        var files = e.target.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
        // Reset input so the same file can be re-selected
        fileInput.value = '';
    });

})();
