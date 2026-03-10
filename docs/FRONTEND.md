# Frontend

## Overview

Vanilla JS single-page application served by Nginx. No framework, no build step, no bundler. Three distinct UI states: upload, processing, and results+chat.

## Stack

| Concern | Choice |
|---|---|
| Language | Vanilla JS (ES6+) |
| Styling | CSS custom properties, dark theme |
| Server | Nginx (static files + API proxy) |
| No dependencies | No npm, no node_modules |

## File Structure

```
frontend/
├── index.html
├── style.css
├── app.js
├── nginx.conf       Proxies /api/* to backend:8000
└── Dockerfile
```

## UI States

### State 1: Upload
Default view on load.

```
┌────────────────────────────────────────┐
│        Air-Gapped Document Analyzer    │
│  Your document never leaves our        │
│      private infrastructure.           │
│                                        │
│   ┌──────────────────────────────┐     │
│   │                              │     │
│   │   Drop PDF, TXT, or DOCX     │     │
│   │   or click to browse         │     │
│   │                              │     │
│   └──────────────────────────────┘     │
│                                        │
│   100% privately hosted —              │
│   no cloud, no third parties           │
│   Zero cloud dependencies              │
└────────────────────────────────────────┘
```

- Drag-over state changes drop zone border/background
- File type and size validated client-side before upload
- On valid file select: transition to processing state

### State 2: Processing
Replaces upload view. No user interaction during this state.

```
┌────────────────────────────────────────┐
│                                        │
│         Analyzing document...          │
│         [spinner / progress bar]       │
│                                        │
│   Processing on private infrastructure │
│   No cloud. No third parties.          │
│                                        │
└────────────────────────────────────────┘
```

- Spinner or animated indicator visible
- Sovereignty message reinforced here intentionally
- No cancel button in v1

### State 3: Results + Chat
Displayed after successful `/api/analyze` response.

```
┌────────────────────────────────────────┐
│  Summary                               │
│  ─────────────────────────────────     │
│  [3-5 sentence summary text]           │
│                                        │
│  Key Points                            │
│  ─────────────────────────────────     │
│  • [point]                             │
│  • [point]                             │
│  • [point]                             │
│                                        │
│  Ask a question about this document    │
│  ┌──────────────────────────┐  [Send]  │
│  └──────────────────────────┘          │
│                                        │
│  [chat history renders above input]    │
│                                        │
│  ─────────────────────────────────     │
│  Powered by qwen3.5:35b - No external  │
│  APIs          [Analyze another doc]   │
└────────────────────────────────────────┘
```

- "Analyze another document" resets to upload state and clears session
- Chat history scrolls within a fixed-height container
- User messages right-aligned, assistant messages left-aligned

## app.js Structure

```
app.js
├── State management      currentState: 'upload' | 'processing' | 'results'
├── Upload handlers       drag/drop events, file input change, validation
├── API calls             analyzeDocument(), sendChatMessage()
├── Render functions      showUpload(), showProcessing(), showResults()
└── Chat handlers         appendMessage(), handleChatSubmit()
```

No classes required — module-level functions and a single state object is sufficient.

## API Communication

All API calls go to `/api/*` which Nginx proxies to the backend. The frontend never references `backend:8000` directly.

```js
// Analyze
const res = await fetch('/api/analyze', {
  method: 'POST',
  body: formData  // multipart, file field
})
const { session_id, summary, key_points } = await res.json()

// Chat
const res = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ session_id, question })
})
const { answer } = await res.json()
```

`session_id` is stored in a module-level variable for the duration of the session. Not persisted to localStorage.

## Nginx Configuration

```nginx
server {
  listen 80;
  server_name _;

  root /usr/share/nginx/html;
  index index.html;

  client_max_body_size 50m;

  location / {
    try_files $uri $uri/ /index.html;
  }

  location /api/ {
    proxy_pass http://backend:8000/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 120s;
    proxy_send_timeout 120s;
  }
}
```

## Design Tokens (CSS Custom Properties)

```css
:root {
  --bg-primary:    #0d0d0d;
  --bg-surface:    #1a1a1a;
  --bg-elevated:   #242424;
  --border:        #2e2e2e;
  --text-primary:  #f0f0f0;
  --text-muted:    #888888;
  --accent:        #00e5ff;   /* ailab.ph cyan */
  --accent-dim:    #00b8cc;
  --error:         #ff4444;
  --radius:        8px;
  --font:          'Inter', system-ui, sans-serif;
}
```

## Required Messaging Placement

| Phrase | Location |
|---|---|
| "Air-Gapped Document Analyzer" | Page title / hero heading |
| "Your document never leaves our private infrastructure" | Upload state subtitle + processing state |
| "100% privately hosted — no cloud, no third parties" | Upload state footer |
| "Zero cloud dependencies" | Upload state footer |
| "Powered by [model] - No external APIs" | Results state footer |
