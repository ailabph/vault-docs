# North Star

## The Problem We're Solving

Every time a user sends a document to a cloud AI API, that document leaves their machine. It touches a vendor's servers, potentially gets logged, potentially enters a training pipeline, and definitely crosses a network boundary the user doesn't control.

For individuals, this is a privacy concern. For regulated industries — legal, finance, healthcare, government — this is a compliance violation. For organizations in air-gapped environments, it's simply not an option.

The common assumption is that you must trade capability for sovereignty. That you need the cloud to get good AI.

**vault-docs exists to disprove that assumption.**

## What We're Proving

Modern open-weight models running on commodity hardware are capable enough to deliver real value on real documents. You don't need OpenAI. You don't need Anthropic. You don't need any external dependency.

This is not a research demo. It is a working, deployable tool that anyone can run with a single command.

## Strategic Context

vault-docs is the first release in aiLab.ph's **Weekly Proof of Product** series. Each release is:

- A working open-source tool, not a prototype
- A public demonstration of a sovereign AI capability
- A shareable artifact for LinkedIn, GitHub, and the ailab.ph blog

The series establishes aiLab.ph's credibility in the air-gapped AI space before the market catches up. Being early and being correct matters more than being polished.

## Success Defined

This release succeeds if:

1. A person can bring up the full stack with `docker compose up` on the VPS once the GPU server and SSH tunnel are bootstrapped
2. They upload a document and receive a summary in under 30 seconds
3. They feel confident their document never touched a public cloud or third-party service — not because we told them, but because the interface makes it obvious
4. The screenshot is worth sharing

## What We Are Not Building

- A product for end consumers
- A multi-user platform
- A document storage system
- An enterprise feature set

This is a proof. It must work well and look good. Everything else is out of scope for this release.

## Guiding Principles

**Sovereignty over convenience.** Every architectural decision favors keeping data local, even at the cost of features.

**Working over impressive.** A tool that actually runs beats a demo that looks amazing but breaks in practice.

**Simple enough to trust.** If the architecture is too complex to explain in a paragraph, it's too complex to trust in an air-gapped environment.

**Open by default.** Apache 2.0. No telemetry. No license checks. No phoning home.
