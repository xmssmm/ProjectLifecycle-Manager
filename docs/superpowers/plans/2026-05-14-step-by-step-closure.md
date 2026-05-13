# Step-by-Step Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or test-driven inline execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `docs/step by step.txt` executable as the V2 end-to-end acceptance scenario.

**Architecture:** Keep the existing project, phase, payment, and acceptance-step services. Close only the gaps found during verification: single-operator review, participant phase operation, guided close buttons, payment/post-review ordering, and user-facing wording for split acceptance.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, pytest, Vue 3, Pinia, Element Plus, Vitest, TypeScript, PowerShell on Windows.

---

## Tasks

- [x] Add backend failing tests for single active department-manager self-review and participant phase promotion.
- [x] Add backend failing tests for payment phase and post-review phase ordering that matches the step-by-step script.
- [x] Add frontend failing tests for main/sub project close buttons and single-operator review visibility.
- [x] Implement minimal backend rule changes.
- [x] Implement minimal frontend API/store/detail-page changes.
- [x] Update V2 validation/spec/user/admin docs with the final closure status.
- [x] Run backend and frontend regression checks.
