---
title: Canvas & Director
---

# Canvas & Director

The canvas is a first-class workspace for node graphs. A canvas can be saved, reopened, imported, and exported as JSON or converted from ComfyUI API Format.

## Nodes and groups

- Add nodes, connect outputs to inputs, and reuse nodes across canvases.
- The ownership group keeps related function nodes together.
- Auto layout keeps sibling order stable; first/last frame order is preserved.
- Canvas files can be imported from the canvas page or Settings -> Workflow Packs.

## Director panel

The director panel is a chat surface beside the graph. Use it to plan shots, reference nodes with `@`, and ask the agent to create or connect nodes. Skills can be enabled, disabled, uploaded, or deleted; uploads follow the Agent Skills layout (`SKILL.md` plus optional references/assets/scripts).

## Bindings and preflight

A variable can feed one or more slots. Media type mismatches are reported explicitly before execution. Preflight checks required inputs, models, and connections; run state and failure locations stay visible on the graph.

## Running

Press Run to execute the selected nodes or the full graph. Results return to the canvas and the asset library. Long video jobs split and join automatically according to the workflow pack.
