#!/usr/bin/env python3
"""
Swimlane diagram skeleton generator for Excalidraw.

Generates a parameterized swimlane template with:
- Title area
- Phase header row (columns)
- Role label sidebar + row backgrounds
- Legend bar
- All structural elements pass validate_geometry.py

Usage:
    python swimlane-template.py                          # default 5 phases × 3 roles
    python swimlane-template.py --phases 8 --output my.excalidraw.json
    python swimlane-template.py --config config.json     # full customization

Config JSON format:
{
  "title": "流程标题",
  "subtitle": "副标题说明",
  "phases": [
    {"name": "① 阶段一", "color": "#5b21b6"},
    {"name": "② 阶段二", "color": "#1e40af"}
  ],
  "roles": [
    {"name": "角色A", "bg": "#fef3c7", "stroke": "#b45309"},
    {"name": "角色B", "bg": "#dbeafe", "stroke": "#1e40af"}
  ]
}
"""

import json
import sys
import argparse
import random

# ── Layout constants ──────────────────────────────────────────────

GRID = 20
CANVAS_BG = "#ffffff"

TITLE_X = 200
TITLE_Y = 20
TITLE_FONT_SIZE = 36
SUBTITLE_FONT_SIZE = 18

PHASE_HEADER_Y = 120
PHASE_HEADER_H = 40
PHASE_COL_W = 200
PHASE_COL_GAP = 40
PHASE_STRIDE = PHASE_COL_W + PHASE_COL_GAP  # 240
PHASE_START_X = 170

LABEL_X = 10
LABEL_W = 130

ROW_START_Y = 180
ROW_H = 200
ROW_GAP = 20
ROW_BG_X = 150
ROW_STROKE = "#e9ecef"
ROW_BG_OPACITY = 15

LEGEND_H = 48
LEGEND_BG_COLOR = "#f8f9fa"
LEGEND_BOX_SIZE = 16

STROKE_WIDTH = 2

# ── Default palettes ─────────────────────────────────────────────

DEFAULT_PHASE_COLORS = [
    "#5b21b6", "#6d28d9", "#1e40af", "#b45309",
    "#5b21b6", "#1e40af", "#5b21b6", "#047857",
    "#047857", "#047857", "#5b21b6", "#6d28d9",
]

DEFAULT_ROLES = [
    {"name": "角色 A\n（外部）",  "bg": "#fef3c7", "stroke": "#b45309", "legend_label": "角色A操作"},
    {"name": "角色 B\n（内部）",  "bg": "#dbeafe", "stroke": "#1e40af", "legend_label": "角色B操作"},
    {"name": "角色 C\n（管理）",  "bg": "#a7f3d0", "stroke": "#047857", "legend_label": "角色C操作"},
]

SYSTEM_ROLE = {
    "name": "系统自动",
    "bg": "#ddd6fe",
    "stroke": "#6d28d9",
    "legend_label": "系统自动",
    "height": 120,
    "font_size": 14,
}


def _seed():
    return random.randint(100000, 999999)


def _make_rect(id_, x, y, w, h, fill, stroke, bound_text_id=None,
               opacity=100, fill_style="solid", roundness=True):
    el = {
        "type": "rectangle",
        "id": id_,
        "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke,
        "backgroundColor": fill,
        "fillStyle": fill_style,
        "strokeWidth": STROKE_WIDTH,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": opacity,
        "angle": 0,
        "seed": _seed(),
        "version": 1,
        "versionNonce": _seed(),
        "isDeleted": False,
        "groupIds": [],
        "boundElements": [],
        "link": None,
        "locked": False,
    }
    if roundness:
        el["roundness"] = {"type": 3}
    if bound_text_id:
        el["boundElements"] = [{"id": bound_text_id, "type": "text"}]
    return el


def _make_text(id_, x, y, w, h, text, font_size=16, align="center",
               v_align="middle", color="#374151", container_id=None):
    return {
        "type": "text",
        "id": id_,
        "x": x, "y": y, "width": w, "height": h,
        "text": text,
        "originalText": text,
        "fontSize": font_size,
        "fontFamily": 3,
        "textAlign": align,
        "verticalAlign": v_align,
        "strokeColor": color,
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "angle": 0,
        "seed": _seed(),
        "version": 1,
        "versionNonce": _seed(),
        "isDeleted": False,
        "groupIds": [],
        "boundElements": None,
        "link": None,
        "locked": False,
        "containerId": container_id,
        "lineHeight": 1.25,
    }


def _make_line(id_, x, y, points, color="#e9ecef", style="dashed", width=1):
    dx = points[-1][0] - points[0][0]
    dy = points[-1][1] - points[0][1]
    return {
        "type": "line",
        "id": id_,
        "x": x, "y": y,
        "width": abs(dx), "height": abs(dy),
        "strokeColor": color,
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": width,
        "strokeStyle": style,
        "roughness": 0,
        "opacity": 100,
        "angle": 0,
        "seed": _seed(),
        "version": 1,
        "versionNonce": _seed(),
        "isDeleted": False,
        "groupIds": [],
        "boundElements": None,
        "link": None,
        "locked": False,
        "points": points,
    }


def generate_swimlane(phases, roles, title="流程标题", subtitle="副标题说明",
                       include_system_row=True):
    elements = []
    n_phases = len(phases)

    # ── Derived dimensions ────────────────────────────────────────
    total_phase_w = n_phases * PHASE_COL_W + (n_phases - 1) * PHASE_COL_GAP
    row_bg_w = total_phase_w + 40  # 20px padding each side

    all_roles = list(roles)
    if include_system_row:
        all_roles.append(SYSTEM_ROLE)

    # ── 1. Title ──────────────────────────────────────────────────
    title_w = min(total_phase_w, 800)
    title_x = PHASE_START_X + (total_phase_w - title_w) // 2

    elements.append(_make_text(
        "title_main", title_x, TITLE_Y, title_w, 45, title,
        font_size=TITLE_FONT_SIZE, align="center", v_align="top",
        color="#1e40af"
    ))
    elements.append(_make_text(
        "title_sub", title_x, TITLE_Y + 50, title_w, 25, subtitle,
        font_size=SUBTITLE_FONT_SIZE, align="center", v_align="top",
        color="#64748b"
    ))

    # ── 2. Phase headers ─────────────────────────────────────────
    for i, phase in enumerate(phases):
        px = PHASE_START_X + i * PHASE_STRIDE
        name = phase.get("name", f"阶段 {i+1}")
        color = phase.get("color", DEFAULT_PHASE_COLORS[i % len(DEFAULT_PHASE_COLORS)])

        rect_id = f"phase_{i}_rect"
        text_id = f"phase_{i}_text"

        elements.append(_make_rect(
            rect_id, px, PHASE_HEADER_Y, PHASE_COL_W, PHASE_HEADER_H,
            fill=color, stroke=color, bound_text_id=text_id,
            roundness=False
        ))
        lines = name.count("\n") + 1
        text_h = lines * SUBTITLE_FONT_SIZE * 1.25
        elements.append(_make_text(
            text_id, px + 5, PHASE_HEADER_Y + (PHASE_HEADER_H - text_h) / 2,
            PHASE_COL_W - 10, text_h, name,
            font_size=SUBTITLE_FONT_SIZE, color="#ffffff",
            container_id=rect_id
        ))

    # ── 3. Role rows (backgrounds + labels) ──────────────────────
    cur_y = ROW_START_Y
    for i, role in enumerate(all_roles):
        h = role.get("height", ROW_H)
        bg_color = role.get("bg", "#f1f3f5")
        stroke_color = role.get("stroke", "#64748b")
        fs = role.get("font_size", 16)

        # Background
        elements.append(_make_rect(
            f"role_{i}_bg", ROW_BG_X, cur_y, row_bg_w, h,
            fill=bg_color, stroke=ROW_STROKE,
            opacity=ROW_BG_OPACITY, roundness=False
        ))

        # Label container
        label_rect_id = f"role_{i}_label"
        label_text_id = f"role_{i}_text"
        elements.append(_make_rect(
            label_rect_id, LABEL_X, cur_y, LABEL_W, h,
            fill=bg_color, stroke=stroke_color,
            bound_text_id=label_text_id, roundness=False
        ))

        role_name = role.get("name", f"角色 {i+1}")
        lines = role_name.count("\n") + 1
        text_h = lines * fs * 1.25
        elements.append(_make_text(
            label_text_id, LABEL_X + 5, cur_y + (h - text_h) / 2,
            LABEL_W - 10, text_h, role_name,
            font_size=fs, color=stroke_color,
            container_id=label_rect_id
        ))

        cur_y += h + ROW_GAP

    # ── 4. Legend bar ────────────────────────────────────────────
    legend_y = cur_y + 10
    legend_w = row_bg_w + LABEL_W + 20

    elements.append(_make_rect(
        "legend_bg", LABEL_X, legend_y, legend_w, LEGEND_H,
        fill=LEGEND_BG_COLOR, stroke=ROW_STROKE,
        roundness=False
    ))

    elements.append(_make_text(
        "legend_title", LABEL_X + 20, legend_y + 14, 50, 20, "图例：",
        font_size=14, align="left", v_align="top", color="#374151"
    ))

    legend_x = LABEL_X + 90
    for i, role in enumerate(all_roles):
        bg_color = role.get("bg", "#f1f3f5")
        stroke_color = role.get("stroke", "#64748b")
        label = role.get("legend_label", role.get("name", "").replace("\n", ""))

        elements.append(_make_rect(
            f"legend_box_{i}", legend_x, legend_y + 16, LEGEND_BOX_SIZE, LEGEND_BOX_SIZE,
            fill=bg_color, stroke=stroke_color, roundness=False
        ))
        elements.append(_make_text(
            f"legend_label_{i}", legend_x + LEGEND_BOX_SIZE + 6, legend_y + 14,
            len(label) * 14, 20, label,
            font_size=12, align="left", v_align="top", color="#374151"
        ))
        legend_x += len(label) * 14 + LEGEND_BOX_SIZE + 40

    # ── 5. Assemble file ─────────────────────────────────────────
    return {
        "type": "excalidraw",
        "version": 2,
        "source": "swimlane-template-generator",
        "elements": elements,
        "appState": {
            "gridSize": GRID,
            "viewBackgroundColor": CANVAS_BG,
        },
        "files": {},
    }


def main():
    parser = argparse.ArgumentParser(description="Generate swimlane diagram skeleton")
    parser.add_argument("--phases", type=int, default=5,
                        help="Number of phase columns (ignored if --config is used)")
    parser.add_argument("--roles", type=int, default=3,
                        help="Number of role rows excluding system (ignored if --config)")
    parser.add_argument("--title", default="流程标题")
    parser.add_argument("--subtitle", default="副标题说明")
    parser.add_argument("--no-system-row", action="store_true",
                        help="Omit the system/automation row")
    parser.add_argument("--config", help="JSON config file for full customization")
    parser.add_argument("--output", "-o", default="swimlane.excalidraw.json",
                        help="Output file path")
    args = parser.parse_args()

    if args.config:
        with open(args.config) as f:
            cfg = json.load(f)
        phases = cfg.get("phases", [{"name": f"阶段 {i+1}"} for i in range(5)])
        roles = cfg.get("roles", DEFAULT_ROLES[:3])
        title = cfg.get("title", args.title)
        subtitle = cfg.get("subtitle", args.subtitle)
        include_sys = cfg.get("include_system_row", True)
    else:
        phases = [{"name": f"阶段 {i+1}",
                    "color": DEFAULT_PHASE_COLORS[i % len(DEFAULT_PHASE_COLORS)]}
                  for i in range(args.phases)]
        roles = DEFAULT_ROLES[:min(args.roles, len(DEFAULT_ROLES))]
        if args.roles > len(DEFAULT_ROLES):
            for j in range(len(DEFAULT_ROLES), args.roles):
                roles.append({
                    "name": f"角色 {j+1}",
                    "bg": "#f1f3f5",
                    "stroke": "#64748b",
                    "legend_label": f"角色{j+1}操作",
                })
        title = args.title
        subtitle = args.subtitle
        include_sys = not args.no_system_row

    data = generate_swimlane(phases, roles, title, subtitle, include_sys)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    n_el = len(data["elements"])
    print(f"✓ Generated {args.output} ({n_el} elements, {len(phases)} phases × {len(roles)} roles)")


if __name__ == "__main__":
    main()
