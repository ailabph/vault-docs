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

    function appendStreamToken(token, done) {
        streamState.buffer += token;

        // --- Detect <think> open tag ---
        var thinkOpen = streamState.buffer.indexOf('<think>');
        if (thinkOpen !== -1 && !streamState.thinking && !streamState.thinkingEl) {
            streamState.thinking = true;
            ensureThinkingBlock();
            // Remove <think> from buffer so it doesn't display
            streamState.buffer = streamState.buffer.replace('<think>', '');
            // Re-derive token without the tag for display
            token = token.replace('<think>', '');
        }

        // --- Detect </think> close tag ---
        var thinkClose = streamState.buffer.indexOf('</think>');
        if (thinkClose !== -1 && streamState.thinking) {
            streamState.thinking = false;
            // Remove </think> from buffer
            streamState.buffer = streamState.buffer.replace('</think>', '');
            token = token.replace('</think>', '');

            // Flush remaining token text into thinking block before collapsing
            if (token && streamState.thinkingContentEl) {
                streamState.thinkingContentEl.textContent += token;
                token = ''; // consumed
            }

            // Collapse thinking block
            if (streamState.thinkingEl) {
                streamState.thinkingEl.classList.add('collapsed');
                // Update label to indicate it's expandable
                var label = streamState.thinkingEl.querySelector('.thinking-label');
                if (label) {
                    label.textContent = '\u{1F9E0} Thinking (click to expand)';
                }
            }

            // Create answer bubble for upcoming answer tokens
            ensureAnswerBubble();

            chatHistory.scrollTop = chatHistory.scrollHeight;
            return;
        }

        // --- Route token to the correct element ---
        if (token) {
            if (streamState.thinking) {
                ensureThinkingBlock();
                streamState.thinkingContentEl.textContent += token;
            } else {
                ensureAnswerBubble();
                streamState.answerEl.textContent += token;
            }
        }

        // --- Finalize on done ---
        if (done) {
            // Edge case: if no answer bubble was created, create one with
            // accumulated non-thinking text
            if (!streamState.answerEl) {
                ensureAnswerBubble();
                // buffer has accumulated text minus think tags
                // answerEl was just created empty — leave it (content already
                // routed token-by-token above, or buffer is all thinking text)
            }
            resetStreamState();
        }

        chatHistory.scrollTop = chatHistory.scrollHeight;
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
