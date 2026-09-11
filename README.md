# MacbookDuo

# 🍎 MacBook Lid → iPhone Duo Effect

> Close your MacBook lid… and watch the screen *fold* in real time — just like Apple’s latest dual-screen concept.

A pure software demo that turns your MacBook’s physical lid angle into a live 3D perspective + depth-of-field effect.  
No extra hardware. No special drivers. Just pure Python magic.

---

### ✨ What it does

- Reads the **real MacBook lid angle** at ~60 Hz  
- Applies a dynamic **perspective warp** that makes the screen look like it’s folding  
- Progressive **Gaussian blur + pure black fade** that spreads from the top as the lid closes  
- Fully transparent, click-through overlay — your desktop stays usable underneath  
- Zero configuration. Just run it and start closing the lid.

Perfect for demos, TikToks, Twitter/X posts, and making people say “wait… how?!”


### 🚀 Quick Start

```bash
# 1. Install dependencies
pip install PyQt5 opencv-python numpy pybooklid

# 2. Run
python main.py
```

Then slowly close your MacBook lid and enjoy the show.

> Requires a modern MacBook with lid angle sensor support (most 2019+ models).

---

### 🛠 How it works (short version)

1. `pybooklid` streams the hinge angle in real time  
2. The current desktop is captured once at launch  
3. OpenCV calculates a perspective transform based on the angle  
4. A progressive blur + black mask is applied from the top edge  
5. Everything is rendered as a frameless, always-on-top, click-through overlay

---

### 📦 Requirements

- macOS
- Python 3.8+
- MacBook with lid angle sensor (most Intel & Apple Silicon models from 2019 onward)

---

### ❤️ Credits

- Sensor access powered by [pybooklid](https://github.com/...)
- Built with love using PyQt5 + OpenCV

---

**Star this repo if it made you smile ⭐**  
