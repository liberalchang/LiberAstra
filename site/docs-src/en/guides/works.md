---
title: Works & Tasks
---

# Works & Tasks

## Assets

Assets -> All / Image / Audio / Video / Subtitle / Text. Search by name, prompt, or time; preview, download, or delete. Canvas intermediate results are hidden by default and can be shown with the toggle.

## Jobs

Jobs shows All / Running / Failed / Completed. Each row has status, time, details, and retry for failures. Retry reuses the original parameters. A job keeps its provider, workflow, parameters, and output links.

## Files

Outputs and uploads live in `data/` (or `/data` in Docker). Deleting an asset removes the file; the related job record remains for lineage.

## Plugins

Resources -> Plugins installs and enables local helpers such as speech and depth. A plugin can create its provider entry automatically; use Settings -> Providers to point at a remote plugin.
