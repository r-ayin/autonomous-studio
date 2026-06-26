#!/usr/bin/env python3
"""index-cases.py — 案例相似度检索（零依赖 TF-IDF，零 LLM token）

修复 Gap 4：MATCH 阶段之前"零检索基础设施，子 agent 只能按文件名读最近 1-2 个案例"。
现在按当前任务描述语义检索 top-k 历史相似案例。

方案：纯 Python TF-IDF + cosine 相似度（无 sklearn/无嵌入模型/无 API）。
- 文档 = 每个 case 的 contextualize.situation + decide.decision_summary
- 查询 = 当前任务/情境描述
- 返回 top-k case 文件名 + 相似度 + 命中关键词

25-1000 个 case 范围内毫秒级，够用。后续可升级 LanceDB + sentence-transformer（见尾部注释）。

用法:
  python3 scripts/index-cases.py --project . search "用户报告 bug，有复现步骤"
  python3 scripts/index-cases.py --project . search --json "冷启动空转"   # JSON 输出供 agent 解析
  python3 scripts/index-cases.py --project . stats                          # 索引统计
"""
import os, sys, json, glob, re, math, argparse
from collections import Counter

# 中英文分词：英文按非字母数字分，中文按字 + 双字组
def tokenize(text):
    if not text:
        return []
    text = text.lower()
    toks = re.findall(r"[a-z0-9_]+|[一-鿿]", text)
    # 中文加双字组（提升语义）
    cn = [t for t in toks if re.match(r"[一-鿿]", t)]
    bigrams = [cn[i] + cn[i + 1] for i in range(len(cn) - 1)]
    return toks + bigrams


def build_index(cases):
    """建 TF-IDF 索引。返回 (docs_tokens, idf, doc_vectors)"""
    docs = []  # [{file, case_id, tokens}]
    for c in cases:
        ctx = c.get("contextualize", {}) or {}
        dec = c.get("decide", {}) or {}
        text = " ".join([
            ctx.get("situation", "") or "",
            ctx.get("active_goal", "") or "",
            dec.get("decision_summary", "") or "",
            " ".join(ctx.get("top_3_concerns", []) or []),
        ])
        docs.append({
            "file": c.get("__file__", ""),
            "case_id": c.get("case_id", ""),
            "tokens": tokenize(text),
        })
    # IDF
    N = len(docs) or 1
    df = Counter()
    for d in docs:
        for t in set(d["tokens"]):
            df[t] += 1
    idf = {t: math.log((N + 1) / (df[t] + 1)) + 1 for t in df}
    # TF-IDF 向量
    for d in docs:
        tf = Counter(d["tokens"])
        d["vec"] = {t: (cnt / max(1, len(d["tokens"]))) * idf.get(t, 1) for t, cnt in tf.items()}
        d["norm"] = math.sqrt(sum(v * v for v in d["vec"].values())) or 1e-9
    return docs, idf


def cosine(qvec, qnorm, doc):
    dot = sum(v * doc["vec"].get(t, 0) for t, v in qvec.items())
    return dot / (qnorm * doc["norm"])


def search(query, docs, idf, k=5):
    qtoks = tokenize(query)
    qtf = Counter(qtoks)
    qvec = {t: (cnt / max(1, len(qtoks))) * idf.get(t, 1) for t, cnt in qtf.items()}
    qnorm = math.sqrt(sum(v * v for v in qvec.values())) or 1e-9
    scored = [(cosine(qvec, qnorm, d), d) for d in docs]
    scored.sort(key=lambda x: -x[0])
    return [(s, d) for s, d in scored[:k] if s > 0]


def load_cases(decisions_dir):
    cases = []
    for cf in sorted(glob.glob(os.path.join(decisions_dir, "case-*.json"))):
        try:
            c = json.load(open(cf, encoding="utf-8"))
            c["__file__"] = os.path.basename(cf)
            cases.append(c)
        except Exception:
            continue
    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--json", action="store_true")
    s.add_argument("--k", type=int, default=5)
    sub.add_parser("stats")

    args = ap.parse_args()
    decisions_dir = os.path.join(args.project, ".claude", "decisions")
    cases = load_cases(decisions_dir)
    docs, idf = build_index(cases)

    if args.cmd == "stats":
        print(f"案例索引统计:")
        print(f"  case 数: {len(docs)}")
        print(f"  词表大小: {len(idf)}")
        print(f"  示例 case: {[d['case_id'] for d in docs[:3]]}")
        return

    if args.cmd == "search":
        results = search(args.query, docs, idf, args.k)
        if args.json:
            print(json.dumps([{"score": round(s, 3), "case_id": d["case_id"], "file": d["file"]}
                              for s, d in results], ensure_ascii=False, indent=2))
        else:
            if not results:
                print("无相似案例")
                return
            print(f"相似案例 top-{len(results)}:")
            for s, d in results:
                print(f"  [{s:.3f}] {d['case_id']} ({d['file']})")


if __name__ == "__main__":
    main()

# 升级路径（P1-b，可选）：若需语义检索质量提升，换 LanceDB + sentence-transformer：
#   import lancedb, sentence_transformers
#   model = SentenceTransformer('BAAI/bge-small-zh')  # 本地中文嵌入，零 API
#   db = lancedb.connect(".claude/decisions/case-index.lance")
#   tbl = db.create_table("cases", data=[{"vec": model.encode(text), "case_id": ...}])
#   tbl.search(model.encode(query)).limit(5).to_list()
