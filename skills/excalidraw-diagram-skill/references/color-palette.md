# Color Palette & Brand Style

**This is the single source of truth for all colors and brand-specific styles.** To customize diagrams for your own brand, edit this file — everything else in the skill is universal.

---

## Shape Colors (Semantic)

Colors encode meaning, not decoration. Each semantic purpose has a fill/stroke pair.

| Semantic Purpose | Fill | Stroke |
|------------------|------|--------|
| Primary/Neutral | `#3b82f6` | `#1e3a5f` |
| Secondary | `#60a5fa` | `#1e3a5f` |
| Tertiary | `#93c5fd` | `#1e3a5f` |
| Start/Trigger | `#fed7aa` | `#c2410c` |
| End/Success | `#a7f3d0` | `#047857` |
| Warning/Reset | `#fee2e2` | `#dc2626` |
| Decision | `#fef3c7` | `#b45309` |
| AI/LLM | `#ddd6fe` | `#6d28d9` |
| Inactive/Disabled | `#dbeafe` | `#1e40af` (use dashed stroke) |
| Error | `#fecaca` | `#b91c1c` |

**Rule**: Always pair a darker stroke with a lighter fill for contrast.

---

## Text Colors (Hierarchy)

Use color on free-floating text to create visual hierarchy without containers.

| Level | Color | Use For |
|-------|-------|---------|
| Title | `#1e40af` | Section headings, major labels |
| Subtitle | `#3b82f6` | Subheadings, secondary labels |
| Body/Detail | `#64748b` | Descriptions, annotations, metadata |
| On light fills | `#374151` | Text inside light-colored shapes |
| On dark fills | `#ffffff` | Text inside dark-colored shapes |

---

## Evidence Artifact Colors

Used for code snippets, data examples, and other concrete evidence inside technical diagrams.

| Artifact | Background | Text Color |
|----------|-----------|------------|
| Code snippet | `#1e293b` | Syntax-colored (language-appropriate) |
| JSON/data example | `#1e293b` | `#22c55e` (green) |

---

## Default Stroke & Line Colors

| Element | Color |
|---------|-------|
| Arrows | Use the stroke color of the source element's semantic purpose |
| Structural lines (dividers, trees, timelines) | Primary stroke (`#1e3a5f`) or Slate (`#64748b`) |
| Marker dots (fill + stroke) | Primary fill (`#3b82f6`) |

---

## Background

| Property | Value |
|----------|-------|
| Canvas background | `#ffffff` |

---

## Visual Consistency Rules

Style choices within a single diagram must be internally consistent. Mixed styles create visual noise and split the viewer's attention between decoding "what does this style mean?" and reading the actual content.

### Line Style Consistency (Stroke Style)

A diagram should use **one dominant line style** for all arrows and connectors. If dashed lines are used anywhere, default all connectors to dashed — mixing solid and dashed implies a semantic distinction that confuses the reader unless explicitly defined in the legend.

| Rule | Rationale |
|------|-----------|
| One stroke style per diagram | Prevents accidental "false signals" — viewers assume style differences carry meaning |
| If dashed is used, unify to dashed | Dashed lines feel lighter and less dominating on dense diagrams; solid connectors competing with dashed ones draw unintended focus |
| Exception: legend-defined contrast | Only mix styles when the legend explicitly assigns meaning (e.g., solid = data flow, dashed = async/optional) |

### Connector Routing (Arrow Shape)

Use **elbow (right-angle) connectors** for structured diagrams like swimlanes, flowcharts, and architecture diagrams. Curved or freeform arrows suit informal sketches but look chaotic in grid-aligned layouts.

| Rule | Rationale |
|------|-----------|
| Elbow connectors for grid layouts | Right angles align with the grid structure, reducing visual entropy |
| Consistent routing across all arrows | One curved arrow among elbowed ones feels like an error, not a design choice |
| Mid-segment offset for parallel arrows | When two arrows share a direction, offset the middle segment to avoid overlap |

### Spacing & Alignment

| Rule | Rationale |
|------|-----------|
| Equal gap between swim lanes | Uneven lanes imply hierarchy or importance where none exists |
| Consistent card/node sizing within a lane | Size variation draws focus — use it intentionally or not at all |
| Whitespace as breathing room | Dense areas need proportionally more margin; crowding makes relationships harder to trace |

### Color Restraint

| Rule | Rationale |
|------|-----------|
| Max 5-6 semantic colors per diagram | Beyond that, the viewer can't maintain a mental color-meaning mapping |
| One color = one meaning, always | Reusing a color for different meanings across regions of the same diagram breaks trust in the visual system |
| Gray/slate for infrastructure, color for roles/decisions | Reserve saturated colors for things the viewer needs to notice |
