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
  - Toggle button in the layer docker toolbar
  <img width="368" height="429" alt="grafik" src="https://github.com/user-attachments/assets/e73aadef-3d47-47f2-a7ff-aa50078c42c6" />

  - Entry in the Layer menu
  <img width="521" height="463" alt="grafik" src="https://github.com/user-attachments/assets/f61c726b-a7fd-45ca-99f2-371082ba2b9d" />

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
- Excluded layers show the **gray/off** icon.
- The default Mode is always on for each new Layer ! if you default off youhave to chage line 26 
  DEFAULT_REMEMBERED = True   # False = opt-in 
  from True to False !!!  

Your brush state is saved **inside the document** into document annotations, so it will always work. 

---

## Requirements

- **Krita 5.0** or newer (tested only on 5.3)
- Python 3 (included with Krita)

---

## Version History

- **1.2.0** — Improved UI integration, better persistence, toolbar button
- **1.0.0** — Initial release
---

**Made with ❤️ for the Krita community**

