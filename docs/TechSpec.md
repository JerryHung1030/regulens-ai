# Regulens-AI Technical Design

This document outlines the design for the **Regulens-AI** desktop application. It was provided as part of the project specification and serves as a reference for future development.

## Overview

Regulens-AI is a Windows desktop tool built with PySide6 that processes regulation JSON files. The application focuses on a single-window, minimalist design. Users will select input files, adjust optional parameters, and trigger the processing.

## Key Points

- **Python 3.11+** with PySide6 UI components.
- Asynchronous operations and pydantic models for validation.
- Results rendered to HTML.
- Logging with rotation via `loguru`.
- Settings stored locally with `QSettings`.

The full specification includes detailed class breakdowns, UI layout, error handling strategy, logging policy, and a suggested milestone schedule.

