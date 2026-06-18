#!/usr/bin/env python3
"""
Layered architecture diagram skeleton generator for Excalidraw.

Generates a parameterized architecture diagram with:
- Title area
- N horizontal layers, each containing M modules
- Dashed container for each layer with label
- Vertical arrows between layers

Usage:
    python architecture-template.py -o output.excalidraw.json
    python architecture-template.py --layers 4 --title "系统架构"
    python architecture-template.py --config config.json

Config JSON format:
{
  "title": "系统架构全景",
  "layers": [
    {
      "name": "用户层",
      "color": "#c2410c",
      "modules": ["Web 端", "移动端", "钉钉小程序"]
    },
    {
      "name": "接入层",
      "color": "#1e40af",
      "modules": ["API 网关", "负载均衡"]
    },
    {
      "name": "业务层",
      "color": "#7c3aed",
      "modules": ["任务服务", "推荐引擎", "调度服务", "通知服务"]
    },
    {
      "name": "数据层",
      "color": "#047857",
      "modules": ["PostgreSQL", "Redis", "对象存储"]
    }
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

MARGIN = 60
TITLE_Y = 20
TITLE_FONT_SIZE = 32

MODULE_W = 140
MODULE_H = 60
MODULE_GAP = 20
MODULE_ROUNDNESS = True

LAYER_PADDING_X = 30
LAYER_PADDING_TOP = 40
LAYER_PADDING_BOTTOM = 20
LAYER_GAP = 40
LAYER_START_Y = 120

LAYER_LABEL_FONT_SIZE = 14
MODULE_FONT_SIZE = 16
STROKE_WIDTH = 2

# ── Layer colors ─────────────────────────────────────────────────

LAYER_COLORS = [
    {"fill": "#fff7ed", "stroke": "#c2410c", "label": "#c2410c"},
    {"fill": "#eff6ff", "stroke": "#1e40af", "label": "#1e40af"},
    {"fill": "#f5f3ff", "stroke": "#7c3aed", "label": "#7c3aed"},
    {"fill": "#f0fdf4", "stroke": "#047857", "label": "#047857"},
    {"fill": "#fefce8", "stroke": "#a16207", "label": "#a16207"},
    {"fill": "#fdf2f8", "stroke": "#be185d", "label": "#be185d"},
]

MODULE_COLORS = [
    {"fill": "#ffffff", "stroke": "#c2410c", "text": "#9a3412"},
    {"fill": "#ffffff", "stroke": "#1e40af", "text": "#1e3a5f"},
    {"fill": "#ffffff", "stroke": "#7c3aed", "text": "#5b21b6"},
    {"fill": "#ffffff", "stroke": "#047857", "text": "#065f46"},
    {"fill": "#ffffff", "stroke": "#a16207", "text": "#854d0e"},
    {"fill": "#ffffff", "stroke": "#be185d", "text": "#9d174d"},
]


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


def _make_rect(id_, x, y, w, h, fill, stroke, bound_text_id=None,
               opacity=100, roundness=True, stroke_style="solid"):
    el = {
        "type": "rectangle",
        "id": id_,
        "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke,
        "backgroundColor": fill,
        "fillStyle": "solid",
        "strokeWidth": STROKE_WIDTH,
        "strokeStyle": stroke_style,
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


def _make_arrow(id_, x, y, points, start_id=None, end_id=None, color="#94a3b8"):
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
            "fixedPoint": [0.5, 1],
        }
    if end_id:
        el["endBinding"] = {
            "elementId": end_id,
            "focus": 0,
            "gap": 4,
            "fixedPoint": [0.5, 0],
        }
    return el


def generate_architecture(layers, title="系统架构"):
    elements = []

    max_modules = max(len(layer.get("modules", [])) for layer in layers)
    max_layer_content_w = max_modules * MODULE_W + (max_modules - 1) * MODULE_GAP
    layer_w = max_layer_content_w + LAYER_PADDING_X * 2
    layer_h = MODULE_H + LAYER_PADDING_TOP + LAYER_PADDING_BOTTOM

    title_w = max(layer_w, 400)
    title_x = MARGIN + (layer_w - title_w) // 2

    elements.append(_make_text(
        "title_main", title_x, TITLE_Y, title_w, 40, title,
        font_size=TITLE_FONT_SIZE, align="center", v_align="top",
        color="#1e40af"
    ))

    layer_rects = []
    cur_y = LAYER_START_Y

    for li, layer in enumerate(layers):
        layer_name = layer.get("name", f"第 {li+1} 层")
        modules = layer.get("modules", [f"模块 {j+1}" for j in range(3)])
        lc = LAYER_COLORS[li % len(LAYER_COLORS)]
        mc = MODULE_COLORS[li % len(MODULE_COLORS)]

        layer_id = f"layer_{li}"
        label_id = f"layer_{li}_label"

        elements.append(_make_rect(
            layer_id, MARGIN, cur_y, layer_w, layer_h,
            fill=lc["fill"], stroke=lc["stroke"],
            opacity=30, roundness=False, stroke_style="dashed"
        ))

        elements.append(_make_text(
            label_id, MARGIN + 10, cur_y + 8, 120, 20, layer_name,
            font_size=LAYER_LABEL_FONT_SIZE, align="left", v_align="top",
            color=lc["label"]
        ))

        n_mods = len(modules)
        total_mods_w = n_mods * MODULE_W + (n_mods - 1) * MODULE_GAP
        mods_start_x = MARGIN + (layer_w - total_mods_w) / 2

        first_mod_id = None
        for mi, mod_name in enumerate(modules):
            mx = mods_start_x + mi * (MODULE_W + MODULE_GAP)
            my = cur_y + LAYER_PADDING_TOP

            mod_id = f"mod_{li}_{mi}"
            mod_text_id = f"mod_{li}_{mi}_text"

            if first_mod_id is None:
                first_mod_id = mod_id

            elements.append(_make_rect(
                mod_id, mx, my, MODULE_W, MODULE_H,
                fill=mc["fill"], stroke=mc["stroke"],
                bound_text_id=mod_text_id
            ))

            text_h = 20
            elements.append(_make_text(
                mod_text_id, mx + 10, my + (MODULE_H - text_h) / 2,
                MODULE_W - 20, text_h, mod_name,
                font_size=MODULE_FONT_SIZE, color=mc["text"],
                container_id=mod_id
            ))

        layer_rects.append({
            "id": layer_id,
            "first_mod": first_mod_id,
            "y": cur_y,
            "h": layer_h,
            "center_x": MARGIN + layer_w / 2,
        })

        cur_y += layer_h + LAYER_GAP

    for i in range(len(layer_rects) - 1):
        upper = layer_rects[i]
        lower = layer_rects[i + 1]

        arrow_id = f"layer_arrow_{i}"
        ax = upper["center_x"]
        ay = upper["y"] + upper["h"]
        dy = LAYER_GAP

        elements.append(_make_arrow(
            arrow_id, ax, ay, [[0, 0], [0, dy]],
            color="#94a3b8"
        ))

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "architecture-template-generator",
        "elements": elements,
        "appState": {
            "gridSize": GRID,
            "viewBackgroundColor": CANVAS_BG,
        },
        "files": {},
    }


DEFAULT_LAYERS = [
    {"name": "用户层", "modules": ["Web 端", "移动端"]},
    {"name": "接入层", "modules": ["API 网关", "负载均衡"]},
    {"name": "业务层", "modules": ["服务 A", "服务 B", "服务 C"]},
    {"name": "数据层", "modules": ["数据库", "缓存", "存储"]},
]


def main():
    parser = argparse.ArgumentParser(description="Generate architecture diagram skeleton")
    parser.add_argument("--layers", type=int, default=4,
                        help="Number of layers (ignored if --config is used)")
    parser.add_argument("--title", default="系统架构")
    parser.add_argument("--config", help="JSON config file for full customization")
    parser.add_argument("--output", "-o", default="architecture.excalidraw.json")
    args = parser.parse_args()

    if args.config:
        with open(args.config) as f:
            cfg = json.load(f)
        layers = cfg.get("layers", DEFAULT_LAYERS)
        title = cfg.get("title", args.title)
    else:
        layers = DEFAULT_LAYERS[:min(args.layers, len(DEFAULT_LAYERS))]
        title = args.title

    data = generate_architecture(layers, title)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    total_mods = sum(len(l.get("modules", [])) for l in layers)
    print(f"✓ Generated {args.output} ({len(data['elements'])} elements, {len(layers)} layers, {total_mods} modules)")


if __name__ == "__main__":
    main()
