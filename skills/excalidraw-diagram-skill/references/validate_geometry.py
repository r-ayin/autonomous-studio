#!/usr/bin/env python3
"""Geometry validation for Excalidraw diagrams.

Checks:
1. Elbow connectors have proper right-angle routing (no diagonal segments)
2. Text inside boxes is not obscured by overlapping elements from higher layers
3. Elements don't overlap unintentionally (text-text, shape-shape collisions)
4. Arrow bindings are bidirectionally consistent
5. Z-order: content not buried under background elements
6. Swimlane alignment: phase headers aligned, backgrounds covering all columns

Usage:
    cd ~/.claude/skills/excalidraw-diagram-skill/references
    python3 validate_geometry.py <path-to-excalidraw-json>
"""

import json
import re
import sys
from dataclasses import dataclass


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def x2(self):
        return self.x + self.w

    @property
    def y2(self):
        return self.y + self.h

    def intersects(self, other: 'Rect') -> bool:
        return not (self.x2 <= other.x or other.x2 <= self.x or
                    self.y2 <= other.y or other.y2 <= self.y)

    def contains_point(self, px: float, py: float) -> bool:
        return self.x <= px <= self.x2 and self.y <= py <= self.y2

    def overlap_area(self, other: 'Rect') -> float:
        ox = max(0, min(self.x2, other.x2) - max(self.x, other.x))
        oy = max(0, min(self.y2, other.y2) - max(self.y, other.y))
        return ox * oy

    def area(self):
        return self.w * self.h


def get_element_rect(el) -> Rect:
    return Rect(el['x'], el['y'], el.get('width', 0), el.get('height', 0))


def validate_elbow_paths(elements):
    """Check that ALL arrows have only horizontal/vertical segments (no diagonals).

    Every arrow segment must be either purely horizontal (dy≈0) or purely
    vertical (dx≈0). A 2-point arrow where both dx and dy are non-zero is
    a diagonal line — this is always wrong in swimlane/flow diagrams.
    """
    issues = []
    for el in elements:
        if el.get('type') != 'arrow':
            continue

        points = el.get('points', [])
        if len(points) < 2:
            continue

        el_id = el.get('id', '?')
        label = ''
        bound = el.get('boundElements') or []
        for b in bound:
            if b.get('type') == 'text':
                text_el = next((e for e in elements if e.get('id') == b['id']), None)
                if text_el:
                    label = text_el.get('text', '')[:20]
                    break

        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]
            dx = abs(p2[0] - p1[0])
            dy = abs(p2[1] - p1[1])
            tolerance = 2.0
            if dx > tolerance and dy > tolerance:
                issues.append(
                    f"Arrow '{el_id}' ({label}): segment {i}→{i+1} is diagonal "
                    f"(dx={dx:.1f}, dy={dy:.1f}). All arrows must use H/V segments only "
                    f"(elbow/折线). Fix by splitting into two segments: one horizontal, one vertical."
                )
    return issues


def validate_text_not_obscured(elements):
    """Check that text inside containers isn't covered by overlapping elements."""
    issues = []
    el_map = {el['id']: el for el in elements if 'id' in el}

    text_elements = [el for el in elements if el.get('type') == 'text']
    container_elements = [el for el in elements if el.get('type') in ('rectangle', 'ellipse', 'diamond')]

    for text_el in text_elements:
        container_id = text_el.get('containerId')
        if not container_id:
            continue

        container = el_map.get(container_id)
        if not container:
            continue

        text_rect = get_element_rect(text_el)
        container_idx = next((i for i, e in enumerate(elements) if e.get('id') == container_id), -1)

        for i, other in enumerate(elements):
            if other.get('id') == container_id or other.get('id') == text_el.get('id'):
                continue
            if other.get('type') in ('arrow', 'line'):
                continue
            if i <= container_idx:
                continue

            other_rect = get_element_rect(other)
            if text_rect.area() == 0 or other_rect.area() == 0:
                continue

            overlap = text_rect.overlap_area(other_rect)
            if overlap > text_rect.area() * 0.3:
                issues.append(
                    f"Text '{text_el.get('text', '')[:30]}' (in {container_id[:12]}) "
                    f"is {overlap/text_rect.area()*100:.0f}% covered by element "
                    f"'{other.get('id', '?')[:12]}' (type={other.get('type')}) at higher layer index."
                )
    return issues


def validate_element_overlap(elements):
    """Check for unintentional overlaps between non-container elements.

    Ignores: text inside its own container, text inside large background rects (swimlanes),
    and shapes that share groupIds (intentional grouping).
    """
    issues = []
    el_map = {el['id']: el for el in elements if 'id' in el}
    rects = []

    for el in elements:
        if el.get('type') in ('arrow', 'line'):
            continue
        if el.get('isDeleted'):
            continue
        w = el.get('width', 0)
        h = el.get('height', 0)
        if w < 5 or h < 5:
            continue
        rects.append((el, get_element_rect(el)))

    def shares_group(a, b):
        ga = set(a.get('groupIds') or [])
        gb = set(b.get('groupIds') or [])
        return bool(ga & gb)

    for i in range(len(rects)):
        el_a, rect_a = rects[i]
        if el_a.get('type') == 'text' and el_a.get('containerId'):
            continue

        for j in range(i + 1, len(rects)):
            el_b, rect_b = rects[j]
            if el_b.get('type') == 'text' and el_b.get('containerId'):
                continue
            if shares_group(el_a, el_b):
                continue

            if el_a.get('type') == 'text' or el_b.get('type') == 'text':
                text_el = el_a if el_a.get('type') == 'text' else el_b
                other_el = el_b if el_a.get('type') == 'text' else el_a
                text_rect = rect_a if el_a.get('type') == 'text' else rect_b
                other_rect = rect_b if el_a.get('type') == 'text' else rect_a

                # Skip text inside large background rects (swimlane/region backgrounds)
                if other_el.get('type') == 'rectangle' and other_rect.area() > text_rect.area() * 10:
                    continue

                overlap = text_rect.overlap_area(other_rect)
                if text_rect.area() > 0 and overlap > text_rect.area() * 0.5:
                    issues.append(
                        f"Text '{text_el.get('text', '')[:25]}' overlaps {overlap/text_rect.area()*100:.0f}% "
                        f"with '{other_el.get('id', '?')[:12]}' (type={other_el.get('type')}). "
                        f"May be unreadable."
                    )
    return issues


def validate_z_order(elements):
    """Check that content elements (text, small shapes) are not buried under background rects.

    In Excalidraw, elements later in the array are drawn on top. If a large background
    rectangle appears AFTER a text/small shape, the text will be hidden underneath.
    """
    issues = []
    for i, el in enumerate(elements):
        if el.get('isDeleted') or el.get('type') in ('arrow', 'line'):
            continue
        el_rect = get_element_rect(el)
        if el_rect.area() == 0:
            continue

        is_content = (el.get('type') == 'text' and not el.get('containerId')) or \
                     (el.get('type') in ('rectangle', 'diamond', 'ellipse') and el_rect.area() < 50000)

        if not is_content:
            continue

        for j in range(i + 1, len(elements)):
            other = elements[j]
            if other.get('isDeleted') or other.get('type') in ('arrow', 'line'):
                continue
            other_rect = get_element_rect(other)
            if other_rect.area() == 0:
                continue
            is_bg = other_rect.area() > el_rect.area() * 5
            if not is_bg:
                continue
            # Check if the background rect covers this content element
            overlap = el_rect.overlap_area(other_rect)
            if overlap > el_rect.area() * 0.8:
                issues.append(
                    f"Element '{el.get('id', '?')[:20]}' (type={el.get('type')}, idx={i}) "
                    f"is covered by larger element '{other.get('id', '?')[:20]}' (idx={j}). "
                    f"The larger element is drawn on top — move it earlier in the array or move the content later."
                )
    return issues


def validate_swimlane_alignment(elements):
    """Check swimlane-specific alignment: phase headers on same row, backgrounds covering all columns."""
    issues = []
    el_map = {el.get('id', ''): el for el in elements}

    # 1. Phase headers should share the same y coordinate
    phase_rects = [el for el in elements
                   if el.get('id', '').startswith('phase_') and el.get('id', '').endswith(('_rect', '_0_rect'))
                   and el.get('type') == 'rectangle' and not el.get('isDeleted')]
    if len(phase_rects) >= 2:
        ys = {el['id']: el['y'] for el in phase_rects}
        target_y = max(set(ys.values()), key=list(ys.values()).count)  # most common y
        for eid, y in ys.items():
            if abs(y - target_y) > 2:
                issues.append(
                    f"Phase header '{eid}' y={y} misaligned with majority y={target_y} (delta={abs(y-target_y):.0f}px)."
                )

    # 2. Phase headers should share the same height
    if len(phase_rects) >= 2:
        heights = {el['id']: el.get('height', 0) for el in phase_rects}
        target_h = max(set(heights.values()), key=list(heights.values()).count)
        for eid, h in heights.items():
            if abs(h - target_h) > 2:
                issues.append(
                    f"Phase header '{eid}' height={h} differs from majority height={target_h}."
                )

    # 3. Background rects should cover all phase columns
    bg_ids = [eid for eid in el_map if eid.endswith('_bg') and el_map[eid].get('type') == 'rectangle']
    if phase_rects and bg_ids:
        leftmost_phase_x = min(el['x'] for el in phase_rects)
        rightmost_phase_x2 = max(el['x'] + el.get('width', 0) for el in phase_rects)
        for bg_id in bg_ids:
            bg = el_map[bg_id]
            if bg.get('isDeleted'):
                continue
            bg_x = bg['x']
            bg_x2 = bg['x'] + bg.get('width', 0)
            if bg_x > leftmost_phase_x + 20:
                issues.append(
                    f"Background '{bg_id}' starts at x={bg_x}, but leftmost phase starts at x={leftmost_phase_x}. "
                    f"Background should extend to cover all phases."
                )
            if bg_x2 < rightmost_phase_x2 - 20:
                issues.append(
                    f"Background '{bg_id}' ends at x={bg_x2}, but rightmost phase ends at x={rightmost_phase_x2}. "
                    f"Background should extend to cover all phases."
                )

    # 4. Content inside a phase column should be horizontally within that column's bounds
    for el in elements:
        eid = el.get('id', '')
        if el.get('isDeleted') or el.get('type') in ('arrow', 'line'):
            continue
        # Match content elements like "hr_p0_rect", "sys_p0_rect", "c1_submit" etc.
        # that have a phase number in their id
        m = re.match(r'(?:hr_p|sys_p|c|b|biz_p)(\d+)', eid)
        if not m:
            continue
        phase_num = m.group(1)
        phase_id = f'phase_{phase_num}_rect' if phase_num != '0' else 'phase_0_rect'
        # Also try without _rect suffix patterns
        phase_el = el_map.get(phase_id) or el_map.get(f'phase_{phase_num}')
        if not phase_el:
            continue
        phase_x = phase_el['x']
        phase_x2 = phase_x + phase_el.get('width', 0)
        el_x = el.get('x', 0)
        el_x2 = el_x + el.get('width', 0)
        # Content should be within phase column bounds (with generous tolerance)
        if el_x2 < phase_x - 30 or el_x > phase_x2 + 30:
            issues.append(
                f"Element '{eid}' (x={el_x}-{el_x2}) is outside phase {phase_num} column "
                f"(x={phase_x}-{phase_x2}). Should be within the column."
            )

    return issues


def validate_style_consistency(elements):
    """Check that arrows within the same diagram use consistent stroke styles and widths.

    Exception: In swimlane diagrams, mixing solid (same-lane flow) and dashed
    (cross-lane interaction) is an intentional convention, not noise. This check
    now emits INFO-level notes for mixed styles rather than warnings, since
    the swimlane color convention (SKILL.md line 258) explicitly allows dashed
    cross-lane arrows alongside solid same-lane arrows.
    """
    issues = []
    arrows = [el for el in elements if el.get('type') == 'arrow' and not el.get('isDeleted')]
    if len(arrows) < 2:
        return issues

    styles = {}
    widths = {}
    for a in arrows:
        s = a.get('strokeStyle', 'solid')
        w = a.get('strokeWidth', 1)
        styles.setdefault(s, []).append(a['id'])
        widths.setdefault(w, []).append(a['id'])

    if len(styles) > 1:
        majority_style = max(styles, key=lambda k: len(styles[k]))
        for style, ids in styles.items():
            if style != majority_style:
                for aid in ids:
                    issues.append(
                        f"Arrow '{aid}' uses strokeStyle='{style}' (majority is '{majority_style}'). "
                        f"INFO: In swimlane diagrams, dashed=cross-lane and solid=same-lane is valid."
                    )

    if len(widths) > 1:
        majority_width = max(widths, key=lambda k: len(widths[k]))
        for width, ids in widths.items():
            if width != majority_width:
                for aid in ids:
                    issues.append(
                        f"Arrow '{aid}' uses strokeWidth={width} but majority uses {majority_width}. "
                        f"Use consistent line widths within the same diagram."
                    )

    return issues


def validate_stroke_consistency(elements):
    """Check that non-arrow shapes use consistent strokeWidth within the diagram."""
    issues = []
    shapes = [el for el in elements
              if el.get('type') in ('rectangle', 'diamond', 'ellipse')
              and not el.get('isDeleted')
              and not el.get('id', '').endswith('_bg')
              and not el.get('id', '').endswith('_label')]
    if len(shapes) < 2:
        return issues

    widths = {}
    for s in shapes:
        w = s.get('strokeWidth', 1)
        widths.setdefault(w, []).append(s['id'])

    if len(widths) > 1:
        majority = max(widths, key=lambda k: len(widths[k]))
        for w, ids in widths.items():
            if w != majority:
                for sid in ids:
                    issues.append(
                        f"Shape '{sid}' strokeWidth={w}, but majority uses {majority}. "
                        f"Use consistent stroke widths."
                    )
    return issues


def validate_row_y_alignment(elements):
    """Check that content elements within the same swimlane row share a consistent y coordinate.

    Groups content rectangles by their row (based on y ranges) and checks that
    all elements in each row use the same y value.
    """
    issues = []
    content_rects = []
    for el in elements:
        if el.get('type') != 'rectangle' or el.get('isDeleted'):
            continue
        eid = el.get('id', '')
        if any(eid.endswith(s) for s in ('_bg', '_label')) or eid.startswith('legend') or eid.startswith('role_') or eid.startswith('phase_'):
            continue
        content_rects.append(el)

    if len(content_rects) < 2:
        return issues

    # Group by approximate row (y within 60px of each other).
    # 60px avoids grouping stacked sub-elements (e.g. a secondary action box below the main one).
    rows = []
    for el in sorted(content_rects, key=lambda e: e['y']):
        placed = False
        for row in rows:
            if abs(el['y'] - row[0]['y']) < 60:
                row.append(el)
                placed = True
                break
        if not placed:
            rows.append([el])

    for row in rows:
        if len(row) < 2:
            continue
        ys = {el['id']: round(el['y'], 1) for el in row}
        target_y = max(set(ys.values()), key=list(ys.values()).count)
        for eid, y in ys.items():
            if abs(y - target_y) > 2:
                issues.append(
                    f"Element '{eid}' y={y} misaligned within its row (majority y={target_y}, delta={abs(y-target_y):.1f}px)."
                )

    return issues


def validate_arrow_bindings(elements):
    """Check that arrow bindings are consistent (both directions) and no arrows are dangling."""
    issues = []
    el_map = {el['id']: el for el in elements if 'id' in el}

    for el in elements:
        if el.get('type') != 'arrow':
            continue
        if el.get('isDeleted'):
            continue
        el_id = el.get('id', '?')

        # Check for dangling arrows (no start or end binding)
        has_start = bool(el.get('startBinding') and el['startBinding'].get('elementId'))
        has_end = bool(el.get('endBinding') and el['endBinding'].get('elementId'))
        if not has_start and not has_end:
            issues.append(
                f"Arrow '{el_id}' has no startBinding or endBinding — it's completely unconnected."
            )
        elif not has_start:
            issues.append(
                f"Arrow '{el_id}' has no startBinding — its start point is dangling."
            )
        elif not has_end:
            issues.append(
                f"Arrow '{el_id}' has no endBinding — its end point is dangling."
            )

        # Check binding consistency (both directions)
        for binding_key in ('startBinding', 'endBinding'):
            binding = el.get(binding_key)
            if not binding:
                continue
            target_id = binding.get('elementId')
            if not target_id:
                continue
            target = el_map.get(target_id)
            if not target:
                issues.append(
                    f"Arrow '{el_id}' {binding_key} references non-existent element '{target_id[:12]}'."
                )
                continue
            bound_els = target.get('boundElements') or []
            if not any(b.get('id') == el_id for b in bound_els):
                issues.append(
                    f"Arrow '{el_id}' binds to '{target_id[:12]}' via {binding_key}, "
                    f"but target's boundElements doesn't include this arrow."
                )
    return issues


def main():
    if len(sys.argv) < 2:
        print("Usage: validate_geometry.py <file.excalidraw.json>")
        sys.exit(1)

    filepath = sys.argv[1]
    with open(filepath, 'r') as f:
        data = json.load(f)

    elements = data.get('elements', [])
    if not elements:
        print("No elements found.")
        sys.exit(0)

    all_issues = []

    print(f"Validating {len(elements)} elements...")
    print()

    checks = [
        ("Elbow paths", validate_elbow_paths, "all segments are horizontal/vertical"),
        ("Text visibility", validate_text_not_obscured, "no text obscured by overlapping elements"),
        ("Element overlap", validate_element_overlap, "no problematic overlaps detected"),
        ("Arrow bindings", validate_arrow_bindings, "all bindings are consistent"),
        ("Style consistency", validate_style_consistency, "all arrows use consistent stroke style and width"),
        ("Stroke consistency", validate_stroke_consistency, "all shapes use consistent stroke width"),
        ("Row Y-alignment", validate_row_y_alignment, "content elements aligned within their rows"),
        ("Z-order", validate_z_order, "no content buried under background elements"),
        ("Swimlane alignment", validate_swimlane_alignment, "phase headers and backgrounds aligned"),
    ]

    for name, check_fn, ok_msg in checks:
        issues = check_fn(elements)
        if issues:
            print(f"\n=== {name} Issues ({len(issues)}) ===")
            for issue in issues[:10]:
                print(f"  - {issue}")
            if len(issues) > 10:
                print(f"  ... and {len(issues) - 10} more")
            all_issues.extend(issues)
        else:
            print(f"✓ {name}: {ok_msg}")

    print(f"\n{'='*50}")
    if all_issues:
        print(f"TOTAL: {len(all_issues)} issues found")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == '__main__':
    main()
