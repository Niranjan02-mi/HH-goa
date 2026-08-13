# 🌴 Frame In Goa — HH Goa 2026 Builder Frame & ID Card Generator

> **Task #1 Submission** for [Hacker House Goa 2026](https://hhgoa.com) shortlisting  
> Generate your personalized HH Goa 2026 builder frame, VIP ID card, and team banner — all client-side, zero uploads.

![Frame In Goa](https://img.shields.io/badge/HH_GOA-2026-00FF88?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgcng9IjIwIiBmaWxsPSIjMEI2ODM5Ii8+PC9zdmc+&labelColor=040d08)
![Built with](https://img.shields.io/badge/Built_with-Vite+Three.js+GSAP-FFD700?style=for-the-badge&labelColor=040d08)

---

## ✦ What This Does

1. **Upload any photo** → auto-crops to fit perfectly
2. **Enter your name + tech stack** → auto-generates a creative Builder Class
3. **Instantly generates:**
   - 📸 **Profile Frame** (1080×1080) — square PFP with branded HH Goa overlay
   - 🪪 **Builder ID Card** (1200×675) — personal badge with name, stack, class, barcodes
   - 👥 **Team Banner** (1500×500) — squad card for up to 3 teammates
4. **1-click download** as PNG
5. **1-click share** to X with pre-filled #FrameInGoa tweet

All processing happens **100% client-side on `<canvas>`** — zero server calls, zero data uploads.

---

## 🚀 How to Generate Your Frame

1. Visit the site
2. Click **"Create Your Frame ✦"** or scroll down to the Generator
3. Drag & drop (or click to browse) your photo
4. Enter your **Name** and select your **Tech Stack**
5. See your auto-generated **Builder Class** (e.g., "ML Alchemist", "Full-Stack Ronin")
6. Click **"Generate Frame ✦"**
7. Download your Frame + ID Card
8. **Post on X** with the pre-filled tweet and **#FrameInGoa**

### 📝 How-To Tweet Template

```
Just generated my HH Goa 2026 Builder Frame! 🌴🚀

Ready to build at India's biggest hack-station.
28–31 OCT 2026, Goa.

Generate yours → [YOUR_DEPLOYED_URL]

#FrameInGoa #HHGoa2026 @247pmstudio
```

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Build Tool | **Vite** |
| 3D Graphics | **Three.js** — particle field + floating wireframe objects |
| Animations | **GSAP ScrollTrigger** — scroll-revealed sections, counter animations |
| Image Compositing | **HTML5 Canvas API** — frame overlay, ID card, team banner |
| Styling | **Vanilla CSS** — glassmorphism, custom properties, responsive |
| Typography | Space Grotesk, JetBrains Mono, Bebas Neue (Google Fonts) |
| Deployment | Works on Vercel, Netlify, GitHub Pages, or any static host |

---

## 📦 Local Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build
```

---

## 🎨 Design Tokens

Matching the official [hhgoa.com](https://hhgoa.com) brand:

- **Primary**: `#0B6839` (Deep green)
- **Accent**: `#00FF88` (Neon green)
- **Gold**: `#FFD700`
- **Background**: `#040d08`
- **Theme color**: `#0B6839`

---

## ✦ Builder Classes

Your Builder Class is auto-generated from your tech stack:

| Stack | Builder Class |
|---|---|
| React / Next.js | Frontend Architect |
| Python / Django | Python Alchemist |
| ML / AI | ML Alchemist |
| Solidity / Web3 | Chain Forger |
| Full-Stack | Full-Stack Ronin |
| DevOps / Cloud | Cloud Nomad |
| UI/UX Design | Pixel Shaman |
| Go | Go Concurrency King |
| Rust | Systems Warlock |
| Mobile | Mobile Artisan |
| Other | Code Warrior |

---

## 📁 Project Structure

```
Hacker_House_GOA/
├── index.html              ← Single-page app
├── package.json
├── vite.config.js
├── public/
│   └── assets/             ← Generated images
├── src/
│   ├── main.js             ← Entry point, all UI wiring
│   ├── style.css           ← Full design system
│   ├── three-scene.js      ← Three.js 3D background
│   ├── animations.js       ← GSAP scroll animations
│   └── canvas-engine.js    ← Canvas compositing engine
└── README.md
```

---

## 🌊 Features

- ✦ **Instantly recognizable** HH Goa 2026 identity
- ✦ **1-click download** + 1-click Share to X
- ✦ **Works on any photo** — no manual cropping
- ✦ **Personalized**: name, stack, auto-generated builder class
- ✦ **Seconds** from upload to shareable output
- ✦ **3D animated background** with Three.js particle field
- ✦ **Scroll animations** via GSAP ScrollTrigger
- ✦ **Team frame** for 1–3 builders
- ✦ **Fully responsive** — works on mobile, tablet, desktop
- ✦ **Zero server calls** — everything runs client-side

---

Built with 🌴 for **Hacker House Goa 2026** · #FrameInGoa
