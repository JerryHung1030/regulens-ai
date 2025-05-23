# Regulens-AI Technical Design

This document outlines the design for the **Regulens-AI** desktop application. It was provided as part of the project specification and serves as a reference for future development.

## Overview

Regulens-AI is a Windows desktop tool built with PySide6 that compares two regulation JSON files using the `RAGCore-X Compare API`. The application focuses on a single-window, minimalist design. Users select two JSON files, adjust optional parameters, trigger the comparison, and export the results as plain text or PDF.

## Key Points

- **Python 3.11+** with PySide6 UI components.
- Asynchronous HTTP requests via `httpx` and pydantic models for validation.
- Markdown results rendered to HTML and optionally to PDF with WeasyPrint.
- Logging with rotation via `loguru`.
- Settings stored locally with `QSettings`.

The full specification includes detailed class breakdowns, UI layout, error handling strategy, logging policy, and a suggested milestone schedule.

