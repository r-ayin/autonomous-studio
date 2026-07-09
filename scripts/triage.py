#!/usr/bin/env python3
"""triage.py — studio 改动 triage + 阶段推进。复杂任务走管线,小修直放。

强制每个改动先声明类型,写 <project>/.pipeline/current.json;
pipeline-gate.py hook 据此决定放行/阻断。

用法:
  triage.py --kind small --desc "修拼写"              小修:直接 development,verify_passed=true
  triage.py --kind complex --desc "加日历"            复杂:stage=requirement,须走完管线
  triage.py --stage prd|development|verify|done       推进阶段(仅前进,不能后退)
  triage.py --verify-passed                           标记 verify 通过(complex commit 前置)
  triage.py --done                                    收尾:stage=done,归档到 .pipeline/history/
  triage.py --show                                    查看当前

studio 项目根 = 最近含 planning/status.json 的祖先目录。
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

STAGES = ["requirement", "prd", "development", "verify", "done"]


def project_root(start: str | None = None) -> Path | None:
    p = Path(start or os.getcwd()).resolve()
    for anc in [p, *p.parents]:
        if (anc / "planning" / "status.json").exists():
            return anc
        if anc.parent == anc:  # reached /
            break
    return None


def current_path(root: Path) -> Path:
    return root / ".pipeline" / "current.json"


def load(root: Path) -> dict | None:
    cp = current_path(root)
    if cp.exists():
        try:
            return json.loads(cp.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, UnicodeDecodeError):
            return None
    return None


def save(root: Path, data: dict) -> None:
    cp = current_path(root)
    cp.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    cp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="studio 改动 triage + 阶段推进")
    ap.add_argument("--kind", choices=["small", "complex"])
    ap.add_argument("--desc", default="")
    ap.add_argument("--stage", choices=STAGES)
    ap.add_argument("--verify-passed", action="store_true")
    ap.add_argument("--done", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--root", default=None, help="override project root")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else project_root()
    if not root:
        print("not a studio project (no planning/status.json ancestor)", file=sys.stderr)
        sys.exit(2)

    if args.show:
        d = load(root)
        print(json.dumps(d, ensure_ascii=False, indent=2) if d else "(no current change)")
        return

    if args.done:
        d = load(root)
        if not d:
            print("no current change to finish")
            return
        d["stage"] = "done"
        d["ended_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        save(root, d)
        hist = root / ".pipeline" / "history"
        hist.mkdir(parents=True, exist_ok=True)
        # ES-M003 fix: glob-count race → timestamp-prefixed filename.
        # ended_at is ISO8601 with seconds precision; replace ':' with '-' for
        # cross-platform filename safety (Windows disallows ':').
        ts_prefix = d["ended_at"].replace(":", "-")
        archive_name = f"{ts_prefix}-{d.get('kind', 'x')}.json"
        (hist / archive_name).write_text(
            json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        # missing_ok=True: 防御 load→unlink 间竞态——另一进程已先行归档并删除
        # current.json 时，本进程正常路径已过 L81-84 前置检查，到此缺失不应致崩溃。
        current_path(root).unlink(missing_ok=True)
        print(f"change done, archived → .pipeline/history/{archive_name}")
        return

    if args.kind:
        stage = "development" if args.kind == "small" else "requirement"
        d = {
            "kind": args.kind,
            "desc": args.desc,
            "stage": stage,
            "verify_passed": True if args.kind == "small" else False,
            "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        save(root, d)
        print(f"triaged: kind={args.kind} stage={stage} desc={args.desc!r}")
        if args.kind == "complex":
            print("复杂任务 → 须走管线: --stage prd → development → verify → --done")
        return

    d = load(root)
    if not d:
        print("no current change; 先 --kind small|complex 声明", file=sys.stderr)
        sys.exit(2)

    if args.stage:
        if STAGES.index(args.stage) < STAGES.index(d.get("stage", "requirement")):
            print(f"阶段不能后退: {d['stage']} → {args.stage}", file=sys.stderr)
            sys.exit(2)
        d["stage"] = args.stage
        save(root, d)
        print(f"stage → {args.stage}")
        return

    if args.verify_passed:
        d["verify_passed"] = True
        save(root, d)
        print("verify_passed = true")
        return

    print(json.dumps(d, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
