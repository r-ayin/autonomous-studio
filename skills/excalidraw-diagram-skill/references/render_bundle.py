"""Render Excalidraw JSON to PNG using Playwright + bundled @excalidraw/excalidraw."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def compute_bounding_box(elements):
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")

    for el in elements:
        if el.get("isDeleted"):
            continue
        x = el.get("x", 0)
        y = el.get("y", 0)
        w = el.get("width", 0)
        h = el.get("height", 0)

        if el.get("type") in ("arrow", "line") and "points" in el:
            for px, py in el["points"]:
                min_x = min(min_x, x + px)
                min_y = min(min_y, y + py)
                max_x = max(max_x, x + px)
                max_y = max(max_y, y + py)
        else:
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x + abs(w))
            max_y = max(max_y, y + abs(h))

    if min_x == float("inf"):
        return (0, 0, 800, 600)

    return (min_x, min_y, max_x, max_y)


def render(excalidraw_path, output_path=None, scale=2, max_width=1920):
    from playwright.sync_api import sync_playwright

    raw = excalidraw_path.read_text(encoding="utf-8")
    data = json.loads(raw)

    elements = [e for e in data["elements"] if not e.get("isDeleted")]
    min_x, min_y, max_x, max_y = compute_bounding_box(elements)
    padding = 80
    diagram_w = max_x - min_x + padding * 2
    diagram_h = max_y - min_y + padding * 2

    vp_width = min(int(diagram_w), max_width)
    vp_height = max(int(diagram_h), 600)

    if output_path is None:
        output_path = excalidraw_path.with_suffix(".png")

    template_path = Path(__file__).parent / "render_bundle.html"
    template_url = template_path.as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": vp_width, "height": vp_height},
            device_scale_factor=scale,
        )

        page.goto(template_url)
        page.wait_for_function("window.__moduleReady === true", timeout=60000)

        json_str = json.dumps(data)
        result = page.evaluate(f"window.renderDiagram({json_str})")

        if not result or not result.get("success"):
            error_msg = result.get("error", "Unknown") if result else "null"
            print(f"ERROR: Render failed: {error_msg}", file=sys.stderr)
            browser.close()
            sys.exit(1)

        page.wait_for_function("window.__renderComplete === true", timeout=15000)

        svg_el = page.query_selector("#root svg")
        if svg_el is None:
            print("ERROR: No SVG element found.", file=sys.stderr)
            browser.close()
            sys.exit(1)

        svg_el.screenshot(path=str(output_path))
        browser.close()

    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", "-o", type=Path, default=None)
    parser.add_argument("--scale", "-s", type=int, default=2)
    parser.add_argument("--width", "-w", type=int, default=1920)
    args = parser.parse_args()

    png_path = render(args.input, args.output, args.scale, args.width)
    print(str(png_path))
