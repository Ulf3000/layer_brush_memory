# Layer Brush & Tool Memory for Krita

A lightweight Krita plugin that remembers your **brush settings and active tool per layer**. Switch freely between paint layers, vector layers, group layers — everything snaps back exactly as you left it.

---

## Features

- **Per-layer brush memory** — restores brush preset, size, opacity, flow, blending mode, and foreground/background colors when you switch layers.
- **Per-layer tool memory** — restores the active tool (brush, text, transform, fill, …) independently of brush memory. Useful for vector layers that always use the text tool, or group layers that always use the transform tool.
- **Two independent toggles** — brush memory and tool memory can be enabled or disabled separately per layer.
- **Default tool on first visit** — layers you've never visited before automatically switch to a sensible default tool based on layer type (e.g. vector layers → text tool, paint layers → brush tool).
- **No polling** — uses Krita's native layer selection signals, zero performance overhead.
- **Persistent storage** — saves all data inside the `.kra` document as an annotation. No external files. Survives save/reopen.
- **Works with multiple open documents.**

---

## UI Integration

### Two toggle buttons in the layer docker

One button for tool memory (`tool.svg`), one for brush memory (`paint.svg`), injected next to the opacity spinner and in the layer toolbar. Active (red) = memory on. Gray = off.

<img width="385" height="463" alt="image" src="https://github.com/user-attachments/assets/c92278b4-f750-41ae-879f-6dee6e184c60" />

### Layer menu entries

Two checkable entries under the **Layer** menu:
- *Remember Tool for this Layer*
- *Remember Brush for this Layer*

<img width="352" height="506" alt="image" src="https://github.com/user-attachments/assets/2935a130-6894-4865-9494-ddc2b91ce559" />

## How It Works

When you switch away from a layer the plugin captures:
- The currently active tool (all layer types)
- The current brush preset, size, opacity, flow, blending mode, and colors (paint layers, masks only)

When you switch to a layer it restores whichever of those are enabled for that layer. Tool is restored first, then brush. If a layer has never been visited before, the tool defaults to a type-appropriate choice (see table below).

| Layer type | Default tool on first visit |
|---|---|
| Paint layer | Brush |
| Vector layer | Text |
| Group layer | Transform |
| Clone layer | Transform |
| Transparency / selection / filter mask | Brush |

---

## Options

All defaults are at the top of `layer_brush_extension.py`:

```python
DEFAULT_TOOL_ON  = True   # tool memory on by default for every new layer
DEFAULT_BRUSH_ON = True   # brush memory on by default for every new layer
```

Set either to `False` for opt-in behavior (memory off until you enable it per layer).

The `_DEFAULT_TOOL_BY_TYPE` dict controls which tool fires on first visit to each layer type. Edit or extend it freely.

---

## Requirements

- **Krita 5.2** or newer (uses `view.currentTool()` and `QButtonGroup` toolbox access)
- Tested on Krita 5.4 alpha

---

## Version History

- **2.0.0** — Split into two independent memories: tool and brush. All layer types eligible for tool memory. Two buttons, two menu entries, two context menu items. Default tool on first visit per layer type. Persistent format updated (backward compatible with 1.x data).
- **1.2.0** — Improved UI integration, better persistence, toolbar button
- **1.0.0** — Initial release

---

**Made with ❤️ for the Krita community**
