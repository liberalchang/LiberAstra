---
title: Settings
---

# Settings

## Providers

Settings -> Providers lists enabled and disabled services. Each provider has a type, base URL, capability tags, key, and concurrency. The API key is encrypted; the UI only shows whether a key exists. Use `http://` for local services; ComfyUI usually needs no key.

## Workflow packs

Settings -> Workflow Packs imports LiberAstra packs, ComfyUI API Format, and canvas JSON. Each row shows the capability, inputs, outputs, and built-in/user status. Same-name user packs override built-ins. Keep model filenames aligned with the pack.

## Prompt templates

Settings -> Prompt Templates edits function templates and scene presets. The optimizer combines a function template (what this task is) with an optional scene preset (style). Built-ins ship with the app; user files only store overrides and custom entries. Identical content stays marked as default. Restore default removes an override, and custom entries can be deleted.

## System

Settings -> System manages the admin account and password, the default LLM used for prompt optimization and scripts, and backup/cleanup. Provider keys remain under Providers.

## Practical defaults

- Configure one working LLM provider before using prompt optimization.
- Import the workflow pack before opening a studio.
- Pin the default model for depth and prompt optimization if you have several providers.
