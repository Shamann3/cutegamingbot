# DESIGN — Admin panel (Atelier)

## World
Dark operate cockpit: pure black canvas, graphite cards, one live accent from the sidebar palette. Hierarchy by brightness and accent glow — never by rainbow chrome.

## Palette
- Void `#000000`
- Card `#0e0e0e` → `#121212`
- Text `#f5f5f5` / `#c4c4c8` / `#8a8a92`
- Accent: user-selected (`--e-accent`), default mint `#7EB89A`

## Type
Manrope 400–800. Tight tracking on titles and metrics. Tabular figures for live numbers.

## Components
Rounded cards (18px), pill tabs/buttons, hairline borders, soft inset highlight. Active nav and primary actions carry accent fill + soft glow. Inputs focus with accent ring.

## Motion
iOS-like spring ease (`cubic-bezier(0.34, 1.45, 0.64, 1)`). Page enter: fade + slight rise + blur. Press: scale 0.96. Respect `prefers-reduced-motion`.

## Cross-surface
Shell, sidebar, topbar, every section root, tables, modals, and mobile bottom bar inherit Atelier via `atelier.css` + accent CSS variables.
