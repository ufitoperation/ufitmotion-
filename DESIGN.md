# DESIGN.md — Ufit Motion Design System

This is the single source of truth for all visual decisions on Ufit Motion. No color, spacing, or component pattern may be used in a template unless it is defined here or explicitly approved by the design-system-architect agent.

---

## Overview

Ufit Motion is a professional operations platform for PE coaches and school administrators. The design should feel trustworthy, energetic, and easy to use in field conditions (mobile, one hand, bright sunlight). Think sports scoreboard meets enterprise dashboard.

Coaches are the primary users. They open this app standing in a gymnasium or on a field, often with one free hand, in the last few minutes before their next class. Every design decision is measured against that reality. High contrast. Large touch targets. Fast paths to the most common actions.

Administrators are the secondary users. They need dense, scannable data — dashboards that answer questions immediately, not pages that ask them to dig.

---

## Colors

### Core Palette

| Token | Hex | Usage |
|---|---|---|
| `--color-primary` | `#1E40AF` | Navigation, primary buttons, headers, key data labels |
| `--color-primary-light` | `#3B82F6` | Hover states, active indicators, focus rings |
| `--color-accent` | `#F59E0B` | CTAs, alerts, highlights, progress indicators |
| `--color-accent-light` | `#FCD34D` | Hover on yellow elements |
| `--color-bg` | `#F8FAFC` | Page background |
| `--color-surface` | `#FFFFFF` | Cards, panels, modals, form backgrounds |
| `--color-surface-dark` | `#1E293B` | Sidebar background, nav background |
| `--color-text-primary` | `#0F172A` | Headings, body text, high-priority labels |
| `--color-text-secondary` | `#64748B` | Labels, captions, secondary information, placeholder text |
| `--color-border` | `#E2E8F0` | Dividers, input borders, table separators |
| `--color-error` | `#EF4444` | Error states, destructive actions, critical alerts |
| `--color-success` | `#22C55E` | Confirmation states, completion indicators, positive trends |
| `--color-warning` | `#F59E0B` | Warnings (same as accent — context determines meaning) |

### Color Rules

- Yellow accent (`--color-accent`) must not exceed 10% of any screen's visual weight. Use it for the one thing that needs to be done next.
- Primary blue is the dominant brand color — use it for structural elements (nav, headers, primary buttons).
- Never use gradients as decorative backgrounds. Gradients are permitted only in data visualizations (charts).
- Never use purple. It is not in the brand palette and creates confusion with status colors.
- Background (`#F8FAFC`) is off-white — do not substitute with pure white (`#FFFFFF`) for page backgrounds. Reserve pure white for surfaces (cards, modals).

---

## Typography

### Font Family

**Inter** — loaded from Google Fonts. Clean, highly legible at small sizes, excellent on mobile screens in variable lighting.

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

For code and data tables: `'Inter Mono', ui-monospace, monospace`

### Type Scale

| Role | Weight | Size | Line Height | Tracking | Usage |
|---|---|---|---|---|---|
| Display | 700 | 32–48px | 1.1 | -0.02em | Hero headings, dashboard stat callouts |
| Heading 1 | 700 | 24px | 1.2 | -0.01em | Page titles |
| Heading 2 | 600 | 20px | 1.3 | 0 | Section headings, card titles |
| Body | 400 | 16px | 1.6 | 0 | All body copy, form labels, descriptions |
| Label/Caption | 500 | 14px | 1.4 | 0.05em (uppercase) | Field labels, table headers, status badges |
| Code/Data | 400 | 14px | 1.5 | 0 | IDs, codes, numeric data tables |

### Typography Rules

- Maximum 2 font weights per screen. Mixing 700 + 400 is the standard pairing. Use 600 for emphasis within a screen that already uses 700 for headings.
- Never replace Inter with another font without an explicit design-system-architect decision recorded in this file.
- Body text minimum size: 16px. Never go below 14px for any text a user needs to read (labels, captions are 14px maximum, not a floor).
- Uppercase is reserved for Label/Caption role only. Do not uppercase body text or headings.

---

## Spacing

### Base Unit

**4px** — all spacing values are multiples of 4.

### Spacing Scale

| Token | Value | Typical Usage |
|---|---|---|
| `--space-1` | 4px | Icon gaps, tight internal padding |
| `--space-2` | 8px | Inline element gaps, compact list items |
| `--space-3` | 12px | Input internal padding (vertical), badge padding |
| `--space-4` | 16px | Form field gaps, default card internal spacing |
| `--space-6` | 24px | Card padding, section element gaps, grid gaps |
| `--space-8` | 32px | Section top/bottom padding (mobile), between major sections |
| `--space-12` | 48px | Section padding (desktop), large vertical rhythm breaks |
| `--space-16` | 64px | Section padding (desktop, page-level), above-the-fold height targets |
| `--space-24` | 96px | Generous top padding for hero or splash-style sections |

### Layout Spacing

| Context | Value |
|---|---|
| Section padding desktop | 64px vertical, 24px horizontal |
| Section padding mobile | 32px vertical, 16px horizontal |
| Card padding | 24px |
| Form field gap | 16px |
| Grid column gap | 24px |
| Sidebar padding | 16px horizontal, 8px vertical (per item) |

---

## Components

### Buttons

#### Primary Button
```css
background: #1E40AF;
color: #FFFFFF;
border-radius: 8px;
height: 44px;
padding: 0 24px;
font-weight: 600;
font-size: 16px;
border: none;
cursor: pointer;
transition: background 150ms ease-out;
```
Hover: `background: #1D4ED8`
Active: `background: #1E3A8A`
Disabled: `opacity: 0.5; cursor: not-allowed`

#### Accent Button
```css
background: #F59E0B;
color: #0F172A;
border-radius: 8px;
height: 44px;
padding: 0 24px;
font-weight: 600;
font-size: 16px;
border: none;
cursor: pointer;
transition: background 150ms ease-out;
```
Hover: `background: #D97706`

#### Ghost Button
```css
background: transparent;
color: #0F172A;
border: 1.5px solid #E2E8F0;
border-radius: 8px;
height: 44px;
padding: 0 24px;
font-weight: 600;
font-size: 16px;
cursor: pointer;
transition: border-color 150ms ease-out, background 150ms ease-out;
```
Hover: `border-color: #94A3B8; background: #F8FAFC`

**Button rules:**
- Minimum height 44px on all buttons — this is a touch target requirement, not a style preference.
- Primary button is for the single most important action on a screen. One primary button per view.
- Accent button for CTAs that should stand out but are not the single primary action (e.g., "Log Session" on a list of sessions).
- Ghost button for secondary and tertiary actions (Cancel, View Details, etc.).

### Cards

```css
background: #FFFFFF;
border-radius: 12px;
box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
padding: 24px;
```

Hover (interactive cards): `box-shadow: 0 4px 12px rgba(0, 0, 0, 0.10); transform: translateY(-1px)`

**Card rules:**
- No card-inside-card nesting. If content within a card needs grouping, use a bordered section (`border: 1px solid #E2E8F0; border-radius: 8px`) instead of another card.
- Cards may have a colored left border to indicate category or status: `border-left: 4px solid <color>`.

### Form Inputs

```css
border: 1.5px solid #E2E8F0;
border-radius: 8px;
height: 44px;
padding: 0 16px;
font-size: 16px;
font-family: Inter, sans-serif;
color: #0F172A;
background: #FFFFFF;
width: 100%;
transition: border-color 150ms ease-out, box-shadow 150ms ease-out;
```
Focus:
```css
border-color: #3B82F6;
box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
outline: none;
```
Error state:
```css
border-color: #EF4444;
box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15);
```

Textarea: same border/focus rules, `min-height: 120px; padding: 12px 16px; resize: vertical`

Select: same as input, with custom chevron icon replacing browser default arrow.

**Input rules:**
- All inputs minimum height 44px for touch targets.
- Field labels are always visible (never placeholder-only). Label above the field, 8px gap.
- Error messages appear below the field in `#EF4444`, 14px, immediately on blur if invalid.
- Never disable browser autocomplete on fields where it is genuinely helpful (name, email).

### Navigation Sidebar

```css
background: #1E293B;
width: 240px;
height: 100vh;
position: fixed;
left: 0;
top: 0;
padding: 16px 0;
```

Nav item (default):
```css
display: flex;
align-items: center;
gap: 12px;
padding: 10px 16px;
color: rgba(255, 255, 255, 0.7);
font-size: 15px;
font-weight: 500;
text-decoration: none;
transition: background 150ms ease-out, color 150ms ease-out;
```

Nav item (active):
```css
color: #FFFFFF;
background: rgba(255, 255, 255, 0.08);
border-left: 3px solid #F59E0B;
padding-left: 13px; /* compensate for border */
```

Nav item (hover):
```css
background: rgba(255, 255, 255, 0.05);
color: #FFFFFF;
```

### Badges / Status Pills

```css
display: inline-flex;
align-items: center;
border-radius: 999px;
padding: 4px 12px;
font-size: 12px;
font-weight: 600;
letter-spacing: 0.03em;
```

Variants:
- Success: `background: #DCFCE7; color: #166534`
- Warning: `background: #FEF3C7; color: #92400E`
- Error: `background: #FEE2E2; color: #991B1B`
- Info: `background: #DBEAFE; color: #1E40AF`
- Neutral: `background: #F1F5F9; color: #475569`

### Tables

```css
width: 100%;
border-collapse: collapse;
font-size: 14px;
```

Header row: `background: #F8FAFC; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; font-size: 12px`

Header/body cells: `padding: 12px 16px; border-bottom: 1px solid #E2E8F0; text-align: left`

Row hover: `background: #F8FAFC`

### Top Navigation Bar

```css
height: 64px;
background: #FFFFFF;
border-bottom: 1px solid #E2E8F0;
padding: 0 24px;
display: flex;
align-items: center;
justify-content: space-between;
position: sticky;
top: 0;
z-index: 100;
```

### Loading States

Every async action must display a loading indicator. Use a spinner on the triggering button (replace button label, keep button disabled) and/or a skeleton loader for the content area that will be populated.

Spinner: 20px SVG, `border: 2px solid rgba(255,255,255,0.3); border-top-color: white; animation: spin 600ms linear infinite`

Skeleton: `background: linear-gradient(90deg, #E2E8F0 25%, #F1F5F9 50%, #E2E8F0 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite`

---

## Layout

### Structural Dimensions

| Element | Value |
|---|---|
| Sidebar width (desktop) | 240px |
| Top nav height | 64px |
| Main content max-width | 1280px |
| Grid columns | 12 |
| Grid gap | 24px |

### Main Content Area

```css
margin-left: 240px; /* sidebar width */
padding: 24px;
min-height: 100vh;
background: #F8FAFC;
```

### Mobile Breakpoint (768px)

At `max-width: 768px`:
- Sidebar hidden (`display: none`)
- Bottom navigation bar appears: `position: fixed; bottom: 0; left: 0; right: 0; height: 64px; background: #1E293B; display: flex; justify-content: space-around; align-items: center`
- Main content: `margin-left: 0; padding: 16px; padding-bottom: 80px` (clear bottom nav)
- Cards stack to single column
- Tables scroll horizontally within a wrapper (`overflow-x: auto`)

### Grid System

12-column grid using CSS Grid:
```css
display: grid;
grid-template-columns: repeat(12, 1fr);
gap: 24px;
```

Common column spans:
- Full width: `grid-column: span 12`
- Half: `grid-column: span 6` (collapses to 12 on mobile)
- Third: `grid-column: span 4` (collapses to 12 on mobile)
- Two-thirds: `grid-column: span 8`
- Quarter: `grid-column: span 3` (collapses to 6 on mobile, 12 on small mobile)

---

## Motion

### Transitions

| Context | Duration | Easing |
|---|---|---|
| Default (buttons, inputs, badges) | 150ms | ease-out |
| Page transitions | 200ms | ease-in-out |
| Sidebar open/close (mobile) | 250ms | ease-in-out |
| Modal appear | 200ms | ease-out |

### Permitted Animated Properties

Animate **only**: `opacity`, `transform` (translate, scale)

Do NOT animate: `width`, `height`, `margin`, `padding`, `max-height` (except for known-height accordion with `transform: scaleY`).

### Animation Philosophy

- Motion communicates state change, not decoration
- Looping animations only for loading states (spinners, skeletons)
- Respect `prefers-reduced-motion: reduce` — wrap all non-essential animations in this media query

---

## Do's

- Use yellow accent sparingly — max 10% visual weight per screen — reserved for CTAs and alerts only.
- Large touch targets on all interactive elements: minimum 44x44px. Coaches tap on phones with potentially gloved hands.
- High contrast text: body text must meet WCAG AA (4.5:1) against its background at minimum. Outdoor use requires this.
- Loading states on every async action — a coach who taps "Submit" must know immediately that something happened.
- Sticky top nav — coaches scroll down long lists; they must always be able to navigate without scrolling back up.
- Use status badges to communicate record state at a glance — coaches scan, not read.

---

## Don'ts

- No purple. Not in the palette. Not as a status color. Not anywhere.
- No gradients as decorative backgrounds. Charts only.
- No glassmorphism (backdrop-filter, frosted glass effects). It reduces contrast in outdoor conditions.
- No Inter replacement without explicit design-system-architect decision and an update to this file.
- No more than 2 font weights per screen.
- No card-inside-card nesting.
- No animations on width, height, margin, or padding.
- No color as the only differentiator for status — always pair color with text or icon for accessibility.
- No disabled form fields without a visible explanation of why the field is disabled.
- No placeholder text as the only label for a form field.
