# MadTech Growth — Brand Specification

> Single source of truth for all visual, verbal, and experiential brand outputs.
> Last updated: 2026-04-22

---

## 1. Identity

| Element | Specification |
|---------|---------------|
| **Company Name** | MadTech Growth |
| **Tagline** | *Generative Engine Optimization for AI-First Search* |
| **Domain** | madtechgrowth.com |
| **Inbound Subdomain** | get.madtechgrowth.com |
| **Industry** | Professional Services + DTC/eCommerce GEO |
| **Positioning** | Authoritative senior consultant. No hedging. No fluff. We diagnose gaps and prescribe fixes. |

### Logo Lockup
- **Wordmark**: "MadTech" in cream (`--cream`), "Growth" in terracotta (`--terracotta`)
- **Font**: DM Serif Display
- **Usage**: Nav header, proposal cover, email signature, landing page hero
- **Clearspace**: Minimum 12px padding around wordmark on digital, 0.25" on print

---

## 2. Color System

### Primary Palette
| Token | Hex | Usage |
|-------|-----|-------|
| `--navy` | `#0B1120` | Primary backgrounds, dark mode base, footer, proposal hero |
| `--terracotta` | `#C45D3E` | CTAs, accents, highlights, active states, "Growth" in logo |
| `--cream` | `#FAF8F5` | Primary text on dark, light section backgrounds |

### Neutral Palette
| Token | Hex | Usage |
|-------|-----|-------|
| `--gray-100` | `#F2F0ED` | Subtle light backgrounds, card hover states |
| `--gray-300` | `#D1CBC3` | Secondary text, borders, disabled states |
| `--gray-500` | `#8A8279` | Tertiary text, metadata, captions |
| `--gray-700` | `#4A4540` | Body text on light backgrounds, dark borders |
| `--navy-light` | `#1a2540` | Elevated cards on navy backgrounds, secondary surfaces |
| `--terracotta-light` | `#d97a5e` | Hover states for terracotta elements |

### Functional / Dataviz Colors
Used only for scoring, status badges, and performance indicators. Never for brand expression.
| Purpose | Hex |
|---------|-----|
| Excellent (8–10) | `#22c55e` |
| Good (6–7.9) | `#84cc16` |
| Fair (4–5.9) | `#eab308` |
| Poor (2–3.9) | `#f97316` |
| Critical (0–1.9) | `#ef4444` |

### Usage Rules
1. **Dark-first**: Default canvas is `--navy`. Light sections are intentional exceptions.
2. **Terracotta is precious**: Use it for CTAs, the word "Growth", and priority badges. Never for large backgrounds.
3. **Contrast minimum**: All text must meet WCAG AA. Cream on navy passes. Gray-300 on navy is for decorative text only.
4. **No black**: `#000000` is banned. Use `--navy` for all "black" needs.
5. **No pure white**: `#FFFFFF` is banned. Use `--cream` for all "white" needs.

---

## 3. Typography

### Font Stack
| Role | Font | Weights | Fallback |
|------|------|---------|----------|
| **Display / Headlines** | DM Serif Display | 400 | Georgia, serif |
| **Body / UI** | Outfit | 300, 400, 500, 600 | system-ui, sans-serif |

### Google Fonts URL
```
https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Outfit:wght@300;400;500;600&display=swap
```

### Type Scale
| Level | Font | Size | Weight | Line-Height | Letter-Spacing | Usage |
|-------|------|------|--------|-------------|----------------|-------|
| H1 | DM Serif Display | `clamp(2.2rem, 5vw, 3.4rem)` | 400 | 1.1 | -0.03em | Page titles, proposal hero |
| H2 | DM Serif Display | `2rem` | 400 | 1.2 | -0.02em | Section headers |
| H3 | Outfit | `1.25rem` | 600 | 1.3 | 0 | Card titles, subsections |
| Body | Outfit | `1rem` (16px) | 400 | 1.6 | 0 | Paragraphs, descriptions |
| Body Small | Outfit | `0.875rem` (14px) | 400 | 1.5 | 0 | Captions, metadata |
| Eyebrow | Outfit | `0.75rem` (12px) | 600 | 1.4 | 0.12em | Labels, tags, uppercase |
| Nav Logo | DM Serif Display | `1.25rem` | 400 | 1 | -0.02em | Header wordmark |

### Typography Rules
1. **Headlines are serif. Everything else is sans.** No exceptions.
2. **Letter-spacing**: Display text is tight (`-0.02em` to `-0.03em`). Eyebrows are wide (`0.12em`). Body is neutral.
3. **No faux bolding** on DM Serif Display. It only has a 400 weight.
4. **Max line length**: 65 characters for body text. Constrain containers to `680px` for readable measure.

---

## 4. Spacing & Layout

### Base Unit
`4px` is the atomic unit. All spacing is a multiple of 4.

### Common Tokens
| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | `4px` | Tight internal padding |
| `--space-2` | `8px` | Inline gaps, icon padding |
| `--space-3` | `12px` | Small component padding |
| `--space-4` | `16px` | Default padding |
| `--space-5` | `24px` | Section gutters |
| `--space-6` | `32px` | Medium section spacing |
| `--space-7` | `48px` | Large section spacing |
| `--space-8` | `64px` | Hero padding |
| `--space-9` | `80px` | Section breaks |

### Container Widths
| Context | Max-Width |
|---------|-----------|
| Reading content | `680px` |
| Standard container | `960px` |
| Wide container | `1200px` |
| Full bleed | `100%` |

### Border Radius
| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | `4px` | Buttons, small cards |
| `--radius-md` | `6px` | Cards, inputs |
| `--radius-lg` | `8px` | Modals, large panels |
| `--radius-pill` | `100px` | Eyebrow badges, tags |

---

## 5. Component Patterns

### Buttons
| Variant | Background | Text | Border | Hover |
|---------|------------|------|--------|-------|
| Primary | `--terracotta` | `--cream` | none | `--terracotta-light` |
| Secondary | transparent | `--cream` | `1px solid --gray-700` | border `--terracotta`, text `--terracotta` |
| Ghost | transparent | `--gray-300` | none | text `--cream` |

**Padding**: `12px 28px` (standard), `10px 20px` (compact)
**Border-radius**: `--radius-sm` (4px)
**Font**: Outfit 500, 0.9rem, letter-spacing 0.02em

### Cards
- Background: `--navy-light`
- Border: `1px solid rgba(255,255,255,0.06)`
- Border-radius: `--radius-md`
- Padding: `--space-5` (24px)
- Shadow: none on dark backgrounds, `0 4px 24px rgba(0,0,0,0.08)` on light backgrounds

### Badges
| Type | Background | Text | Border |
|------|------------|------|--------|
| Priority P1 | `rgba(196,93,62,0.12)` | `--terracotta` | `1px solid rgba(196,93,62,0.3)` |
| Priority P2 | `rgba(234,179,8,0.12)` | `#eab308` | `1px solid rgba(234,179,8,0.3)` |
| Priority P3 | `rgba(138,130,121,0.12)` | `--gray-500` | `1px solid rgba(138,130,121,0.3)` |
| Effort Small | `rgba(34,197,94,0.12)` | `#22c55e` | `1px solid rgba(34,197,94,0.3)` |
| Effort Medium | `rgba(132,204,22,0.12)` | `#84cc16` | `1px solid rgba(132,204,22,0.3)` |
| Effort Large | `rgba(249,115,22,0.12)` | `#f97316` | `1px solid rgba(249,115,22,0.3)` |

---

## 6. Voice & Tone

### Personality
- **Authoritative**: We are the expert in the room. We don't apologize for our expertise.
- **Direct**: Short sentences. Active voice. No filler.
- **Premium**: We serve $10M+ professional services firms and $100M+ DTC brands. Our language signals that caliber.
- **Actionable**: Every observation must include a "so what" and a "what now."

### Lexicon
| Say This | Not This |
|----------|----------|
| GEO audit | SEO checkup |
| gaps | issues / problems |
| prioritized fixes | recommendations |
| AI visibility | ranking |
| structured data | meta tags |
| prescribe | suggest |
| investment | cost / price |
| engagement | project |

### Forbidden Words
- "Just"
- "Simply"
- "Basically"
- "We think..."
- "Maybe"
- "Kind of"
- "Very" (use a stronger adjective instead)
- "Optimize" (overused; use "engineer" or "structure")

### Proposal Tone Checklist
Every audit proposal must:
1. Open with the score — no throat-clearing
2. Name the gap specifically (e.g., "No JSON-LD Organization schema")
3. State the business consequence (e.g., "AI agents cannot verify your firm's NAP consistency")
4. Prescribe the fix with effort estimate
5. Close with a clear CTA and booking link

---

## 7. File Outputs

### Naming Conventions
| Deliverable | Pattern | Example |
|-------------|---------|---------|
| Audit Proposal | `audit_proposal_<domain>_<YYYY-MM-DD>.html` | `audit_proposal_1800nynylaw_com_2026-04-22.html` |
| GEO Snapshot | `geo_snapshot_<domain>_<YYYY-MM-DD>.json` | `geo_snapshot_brettnomberglaw_com_2026-04-22.json` |
| Discovery Report | `discovery_<vertical>_<YYYY-MM-DD>.json` | `discovery_ps_2026-04-22.json` |
| Competitor Comparison | `comp_comparison_<client_domain>_<YYYY-MM-DD>.html` | `comp_comparison_1800nynylaw_com_2026-04-22.html` |

### Print Specifications
- **Paper**: US Letter (8.5" x 11") or A4
- **Margins**: Default browser print margins (0.4"–0.6")
- **Background graphics**: Must be enabled
- **Color mode**: RGB (digital), convert to CMYK if sending to a print shop

---

## 8. Digital Presence

### Email Signature
```
—
MadTech Growth
Generative Engine Optimization
scott@madtechgrowth.com | madtechgrowth.com
Book a call: [calendly link]
```
Font: Outfit 400, 14px, `--gray-500` color. No images.

### Social / Meta
| Platform | Format |
|----------|--------|
| **Open Graph / Twitter** | Navy background, terracotta accent, DM Serif Display headline |
| **LinkedIn** | Personal posts from Scott Krauss, company page for MadTech Growth |
| **Discord** | Automated reports posted to #geo-prospects. Format: markdown, no HTML. |

---

## 9. Implementation Notes for Developers

### When Building a New Deliverable
1. Copy the CSS custom properties from `:root` in `geo-snapshot-landing/index.html`.
2. Use the functional color scale **only** for data visualization (scores, charts).
3. Never introduce a new font. DM Serif Display + Outfit only.
4. Run the output past the **Voice & Tone** section before shipping copy.
5. If proposing a new color, it must map to an existing token or be rejected.

### Files That Must Stay in Sync with This Document
- `geo_audit_proposal.py` — inline brand colors, fonts, spacing
- `geo-snapshot-landing/index.html` — landing page styles
- `geo-snapshot-landing/netlify/functions/geo-snapshot.py` — email template styles
- Any future email templates, outbound sequences, or pitch decks

---

## 10. Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-04-22 | Initial spec from existing proposal + landing page audit | Hermes |
