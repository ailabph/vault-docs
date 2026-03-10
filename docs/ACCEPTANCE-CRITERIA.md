# Acceptance Criteria

These are the conditions that must be true for vault-docs to be considered complete and ready for public release.

---

## Deployment

- [ ] `docker compose up` starts the full stack from a cold state with a single command
- [ ] The application is accessible at the VPS public IP/domain on port `3000` after startup
- [ ] `ollama pull qwen3.5:35b` has been run manually on the GPU server prior to deployment (one-time bootstrap)
- [ ] No manual steps are required on the VPS beyond running `docker compose up`
- [ ] The stack restarts cleanly after `docker compose down && docker compose up`

## Document Upload

- [ ] User can drag and drop a file onto the upload area
- [ ] User can click to browse and select a file
- [ ] Accepted formats: PDF, TXT, DOCX
- [ ] Files over the size limit are rejected with a clear error message
- [ ] Unsupported file types are rejected before processing begins
- [ ] A processing indicator is visible while the document is being analyzed

## Analysis Output

- [ ] Summary is 3–5 sentences in length
- [ ] Key points are returned as a bullet list (minimum 3, maximum 10)
- [ ] Summary and key points are displayed within 30 seconds for a 10-page document (on target hardware)
- [ ] Output is readable and coherent — no garbled or truncated responses

## Chat Interface

- [ ] User can type a question about the document after analysis is complete
- [ ] The LLM responds using the document content as context
- [ ] Chat history is visible within the session
- [ ] Follow-up questions produce contextually accurate responses

## Data Sovereignty

- [ ] Zero outbound HTTP requests are made during document processing (verifiable via network monitor)
- [ ] Ollama API calls are made to `localhost:11434` on the VPS host (via SSH tunnel to GPU server)
- [ ] No document content is written to disk beyond the duration of the request (or clearly scoped temp files)
- [ ] The interface displays all required sovereignty messaging (see UI section below)

## UI & Branding

- [ ] Dark theme matching ailab.ph aesthetic
- [ ] The following phrases appear in the interface:
  - "Air-Gapped Document Analyzer"
  - "Your document never leaves our private infrastructure"
  - "100% privately hosted — no cloud, no third parties"
  - "Zero cloud dependencies"
  - "Powered by [model name] - No external APIs"
- [ ] Interface is screenshot-worthy at 1920x1080

## Code Quality

- [ ] `docker compose up` produces no errors in logs on a clean run
- [ ] Backend returns meaningful HTTP error codes (400 for bad input, 500 for processing failures)
- [ ] No hardcoded model names or hostnames outside of environment variables / config
- [ ] Repository contains no secrets, API keys, or credentials

## Documentation

- [ ] README explains what the tool does in the first paragraph
- [ ] README quick start section produces a working result when followed exactly
- [ ] `docs/` directory contains architecture and infrastructure documentation
- [ ] LICENSE file is Apache 2.0
