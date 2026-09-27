# DESIGN — Admin panel (Epsilon Craft)

## World
CryptoBot-grade dark operate UI: true black canvas, graphite `#1c1c1e` blocks, one live accent from the palette (default soft lavender). Floating capsule dock on phone; full-bleed taskbar dock on desktop. Hierarchy by type weight and accent glow — never rainbow chrome.

## Palette
- Void `#000000`
- Elevated `#1c1c1e` / `#2c2c2e`
- Text `#ffffff` / `#aeaeb2` / `#8e8e93`
- Accent: user-selected (`--e-accent`), photo default `#c8afff`

## Type
Manrope 400–800. Display titles ~2rem / tracking -0.05em. Tabular figures for metrics.

## Layout
- Phone: **no top chrome**. Main tabs only in the floating bottom dock; search / accent / exit live in the menu sheet (dock sliders). Page title sits in content.
- Desktop: every screen fills the viewport; content column max ~1120–1200px centered; taskbar dock full width.

## Components
Pill period controls, bento metric tiles, iOS switches (accent when on), vertical day bars + habit dots, clean people rows with text actions, search field with soft accent ring in the menu sheet.

## Motion
Framer Motion dock entrance; switch spring; 160–220ms ease elsewhere. Respect `prefers-reduced-motion`.
