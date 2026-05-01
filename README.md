# Layer Brush Memory for Krita

A lightweight Krita plugin that **remembers your brush settings per layer**.

Never lose your brush size, opacity, flow, blending mode, or colors when switching between layers again.

---

## Features

- **Automatic per-layer brush memory** — instantly restores brush preset, size, opacity, flow, blending mode, and foreground/background colors when you switch layers.
- **Per-layer toggle** — exclude specific layers from brush memory (great for adjustment layers, reference layers, etc.).
- **No polling** — uses Krita’s native layer selection signals for smooth performance.
- **Persistent storage** — saves brush data inside the `.kra` document using annotations (no external files).
- **Works with multiple documents and survives save/reopen.** 

- **UI integration**:


  **- Toggle button in the layer docker toolbar**
    
  <img width="368" height="429" alt="grafik" src="https://github.com/user-attachments/assets/e73aadef-3d47-47f2-a7ff-aa50078c42c6" />



  **- Entry in the Layer menu**
    
  <img width="521" height="463" alt="grafik" src="https://github.com/user-attachments/assets/f61c726b-a7fd-45ca-99f2-371082ba2b9d" />



---

## How to Use

- The plugin activates automatically when you switch layers.
- Excluded layers show the **gray/off** icon.

  The default Mode is **always on**  for every new Pixel-Layer! 


if you want **default off** youhave to chage line 26 in the script: 
  
DEFAULT_REMEMBERED = True   to  DEFAULT_REMEMBERED = False
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

