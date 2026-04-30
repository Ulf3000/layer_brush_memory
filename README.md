# Layer Brush Memory for Krita

A lightweight Krita plugin that **remembers your brush settings per layer**.

Never lose your brush size, opacity, flow, blending mode, or colors when switching between layers again.

---

## Features

- **Automatic per-layer brush memory** — instantly restores brush preset, size, opacity, flow, blending mode, and foreground/background colors when you switch layers.
- **Per-layer toggle** — exclude specific layers from brush memory (great for adjustment layers, reference layers, etc.).
- **No polling** — uses Krita’s native layer selection signals for smooth performance.
- **Persistent storage** — saves brush data inside the `.kra` document using annotations (no external files).
- **UI integration**:
  - Toggle button next to the layer opacity slider
  - Toggle button in the layer docker toolbar
  - Entry in the Layer menu
  - Context menu option on right-click in the layer list
- Works with multiple documents and survives save/reopen.

---

## Installation

1. Download the latest release or clone this repository.
2. Copy the entire `layer_brush_memory` folder into your Krita plugins directory:
   - **Windows**: `C:\Users\YourName\AppData\Roaming\krita\pykrita`
   - **Linux**: `~/.local/share/krita/pykrita`
   - **macOS**: `~/Library/Application Support/Krita/pykrita`
3. Restart **Krita**.
4. Go to **Settings → Configure Krita → Python Plugin Manager** and **enable** "Layer Brush Memory".

---

## How to Use

- The plugin activates automatically when you switch layers.
- Click the **memory icon** (next to opacity or in the layer toolbar) to **exclude** the current layer from brush memory.
- Excluded layers show the **gray/off** icon.
- Right-click any layer → "Exclude from brush memory" / "Remember brush for this layer".

Your brush state is saved **inside the document**, so it travels with the `.kra` file.

---

## Requirements

- **Krita 5.0** or newer
- Python 3 (included with Krita)

---

## Version History

- **1.2.0** — Improved UI integration, better persistence, toolbar button
- **1.0.0** — Initial release

---

## License

This project is licensed under the **MIT License** — feel free to modify and distribute.

---

## Contributing

Bug reports, feature suggestions, and pull requests are welcome!

---

**Made with ❤️ for the Krita community**

