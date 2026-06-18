#!/usr/bin/env python3
"""
Horizontal flowchart skeleton generator for Excalidraw.

Generates a parameterized flowchart with:
- Title area
- N step nodes (rectangle/ellipse/diamond) connected by arrows
- Auto line-wrap when steps > max_per_row
- All structural elements pass validate_geometry.py

Usage:
    python flowchart-template.py -o output.excalidraw.json
    python flowchart-template.py --steps 7 --title "审批流程"
    python flowchart-template.py --config config.json

Config JSON format:
{
  "title": "流程标题",
  "steps": [
    {"name": "提交申请", "type": "start"},
    {"name": "审核", "type": "step"},
    {"name": "是否通过？", "type": "decision"},
    {"name": "执行", "type": "step"},
    {"name": "完成", "type": "end"}
  ],
  "max_per_row": 5
}

Step types: start (ellipse), end (ellipse), step (rectangle), decision (diamond)
"""

import json
import sys
import argparse
import random

# ── Layout constants ──────────────────────────────────────────────

GRID = 20
CANVAS_BG = "#ffffff"

MARGIN = 60
TITLE_Y = 20
TITLE_FONT_SIZE = 32

UNIT_W = 180
UNIT_H = 80
GAP_X = 80
GAP_Y = 120
MAX_PER_ROW = 5

START_X = MARGIN
START_Y = 120

ARROW_COLOR = "#374151"
STROKE_WIDTH = 2

# ── Color palette ────────────────────────────────────────────────

COLORS = {
    "start":    {"fill": "#fff7ed", "stroke": "#c2410c", "text": "#c2410c"},
    "end":      {"fill": "#f0fdf4", "stroke": "#15803d", "text": "#15803d"},
    "step":     {"fill": "#eff6ff", "stroke": "#1e40af", "text": "#1e3a5f"},
    "decision": {"fill": "#fefce8", "stroke": "#a16207", "text": "#854d0e"},
}


def _seed():
    return random.randint(100000, 999999)


def _cjk_text_width(text, font_size):
    width = 0
    for ch in text:
        if '一' <= ch <= '鿿' or '　' <= ch <= '〿':
            width += font_size * 0.95
        else:
            width += font_size * 0.55
    return max(width, 60)


def _make_rect(id_, x, y, w, h, fill, stroke, bound_text_id=None, roundness=True):
    el = {
        "type": "rectangle",
        "id": id_,
        "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke,
        "backgroundColor": fill,
        "fillStyle": "solid",
        "strokeWidth": STROKE_WIDTH,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
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


def _make_ellipse(id_, x, y, w, h, fill, stroke, bound_text_id=None):
    el = {
        "type": "ellipse",
        "id": id_,
        "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke,
        "backgroundColor": fill,
        "fillStyle": "solid",
        "strokeWidth": STROKE_WIDTH,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
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
    if bound_text_id:
        el["boundElements"] = [{"id": bound_text_id, "type": "text"}]
    return el


def _make_diamond(id_, x, y, w, h, fill, stroke, bound_text_id=None):
    el = {
        "type": "diamond",
        "id": id_,
        "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke,
        "backgroundColor": fill,
        "fillStyle": "solid",
        "strokeWidth": STROKE_WIDTH,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
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


def _make_arrow(id_, x, y, points, start_id=None, end_id=None, color=ARROW_COLOR):
    el = {
        "type": "arrow",
        "id": id_,
        "x": x, "y": y,
        "width": abs(points[-1][0] - points[0][0]) or 1,
        "height": abs(points[-1][1] - points[0][1]) or 1,
        "strokeColor": color,
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": STROKE_WIDTH,
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
        "points": points,
        "lastCommittedPoint": None,
        "startArrowhead": None,
        "endArrowhead": "arrow",
        "elbowed": True,
    }
    if start_id:
        el["startBinding"] = {
            "elementId": start_id,
            "focus": 0,
            "gap": 4,
            "fixedPoint": [1, 0.5],
        }
    if end_id:
        el["endBinding"] = {
            "elementId": end_id,
            "focus": 0,
            "gap": 4,
            "fixedPoint": [0, 0.5],
        }
    return el


def _node_position(index, max_per_row):
    row = index // max_per_row
    col = index % max_per_row
    x = START_X + col * (UNIT_W + GAP_X)
    y = START_Y + row * (UNIT_H + GAP_Y)
    return x, y


def generate_flowchart(steps, title="流程标题", max_per_row=MAX_PER_ROW):
    elements = []
    node_ids = []

    total_cols = min(len(steps), max_per_row)
    total_w = total_cols * UNIT_W + (total_cols - 1) * GAP_X
    title_w = max(total_w, 400)
    title_x = START_X + (total_w - title_w) // 2

    elements.append(_make_text(
        "title_main", title_x, TITLE_Y, title_w, 40, title,
        font_size=TITLE_FONT_SIZE, align="center", v_align="top",
        color="#1e40af"
    ))

    for i, step in enumerate(steps):
        x, y = _node_position(i, max_per_row)
        name = step.get("name", f"步骤 {i+1}")
        stype = step.get("type", "step")
        colors = COLORS.get(stype, COLORS["step"])

        shape_id = f"node_{i}"
        text_id = f"node_{i}_text"
        node_ids.append(shape_id)

        text_w = _cjk_text_width(name, 16)
        node_w = max(UNIT_W, text_w + 40)
        text_h = 20

        if stype in ("start", "end"):
            elements.append(_make_ellipse(
                shape_id, x, y, node_w, UNIT_H,
                fill=colors["fill"], stroke=colors["stroke"],
                bound_text_id=text_id
            ))
        elif stype == "decision":
            dw = max(node_w + 40, 200)
            dh = max(UNIT_H + 20, 100)
            elements.append(_make_diamond(
                shape_id, x - 10, y - 10, dw, dh,
                fill=colors["fill"], stroke=colors["stroke"],
                bound_text_id=text_id
            ))
        else:
            elements.append(_make_rect(
                shape_id, x, y, node_w, UNIT_H,
                fill=colors["fill"], stroke=colors["stroke"],
                bound_text_id=text_id
            ))

        elements.append(_make_text(
            text_id, x + 10, y + (UNIT_H - text_h) / 2,
            node_w - 20, text_h, name,
            font_size=16, color=colors["text"],
            container_id=shape_id
        ))

    for i in range(len(steps) - 1):
        cur_row = i // max_per_row
        next_row = (i + 1) // max_per_row
        cur_x, cur_y = _node_position(i, max_per_row)
        next_x, next_y = _node_position(i + 1, max_per_row)

        arrow_id = f"arrow_{i}_to_{i+1}"

        if cur_row == next_row:
            ax = cur_x + UNIT_W
            ay = cur_y + UNIT_H / 2
            points = [[0, 0], [GAP_X, 0]]
            arrow = _make_arrow(arrow_id, ax, ay, points,
                                start_id=node_ids[i], end_id=node_ids[i + 1])
        else:
            ax = cur_x + UNIT_W / 2
            ay = cur_y + UNIT_H
            mid_y = GAP_Y / 2
            dx = next_x + UNIT_W / 2 - ax
            dy = next_y - ay
            points = [[0, 0], [0, mid_y], [dx, mid_y], [dx, dy]]
            arrow = _make_arrow(arrow_id, ax, ay, points,
                                start_id=node_ids[i], end_id=node_ids[i + 1])

        elements[elements.index(next((e for e in elements if e["id"] == node_ids[i]), None))]["boundElements"].append(
            {"id": arrow_id, "type": "arrow"}
        )
        elements[elements.index(next((e for e in elements if e["id"] == node_ids[i + 1]), None))]["boundElements"].append(
            {"id": arrow_id, "type": "arrow"}
        )
        elements.append(arrow)

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "flowchart-template-generator",
        "elements": elements,
        "appState": {
            "gridSize": GRID,
            "viewBackgroundColor": CANVAS_BG,
        },
        "files": {},
    }


def main():
    parser = argparse.ArgumentParser(description="Generate flowchart diagram skeleton")
    parser.add_argument("--steps", type=int, default=5,
                        help="Number of steps (ignored if --config is used)")
    parser.add_argument("--title", default="流程标题")
    parser.add_argument("--max-per-row", type=int, default=MAX_PER_ROW)
    parser.add_argument("--config", help="JSON config file for full customization")
    parser.add_argument("--output", "-o", default="flowchart.excalidraw.json")
    args = parser.parse_args()

    if args.config:
        with open(args.config) as f:
            cfg = json.load(f)
        steps = cfg.get("steps", [{"name": f"步骤 {i+1}"} for i in range(5)])
        title = cfg.get("title", args.title)
        max_per_row = cfg.get("max_per_row", args.max_per_row)
    else:
        steps = [{"name": f"步骤 {i+1}", "type": "step"} for i in range(args.steps)]
        if steps:
            steps[0]["type"] = "start"
            steps[-1]["type"] = "end"
        title = args.title
        max_per_row = args.max_per_row

    data = generate_flowchart(steps, title, max_per_row)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✓ Generated {args.output} ({len(data['elements'])} elements, {len(steps)} steps)")


if __name__ == "__main__":
    main()
