#!/usr/bin/env python3
"""Score a resume against the screening model.

Usage:
    python3 score_resume.py <pdf_path> [--position <position_type>]

Position types: 执行, 组长, 高阶管理, 食品生鲜
Default: 执行
"""
import sys, os, re, json, argparse

try:
    import pdfplumber
except ImportError:
    os.system("pip install pdfplumber --break-system-packages -q")
    import pdfplumber

POSITIVE_KEYWORDS = {
    'user_perspective': {
        'patterns': [r'用户视角', r'用户体验', r'用户需求', r'用户画像', r'用户角度', r'UX'],
        'weight': 2.5,
        'label': '用户视角'
    },
    'search_eval': {
        'patterns': [r'搜索评测', r'搜索优化', r'搜索引擎', r'搜索结果评测'],
        'weight': 2.5,
        'label': '搜索评测经验'
    },
    'recommendation': {
        'patterns': [r'导购', r'推荐', r'种草', r'商品推荐', r'智能推荐'],
        'weight': 2.0,
        'label': '导购/推荐经验'
    },
    'ai_tech': {
        'patterns': [r'AI', r'人工智能', r'大模型', r'LLM', r'GPT', r'深度学习', r'NLP'],
        'weight': 1.5,
        'label': 'AI/大模型经验'
    },
    'annotation': {
        'patterns': [r'数据标注', r'标注', r'评测', r'测评', r'质检'],
        'weight': 1.5,
        'label': '标注/评测经验'
    },
    'ecommerce': {
        'patterns': [r'电商', r'淘宝', r'天猫', r'京东', r'拼多多', r'抖音电商', r'快手电商'],
        'weight': 1.5,
        'label': '电商经验'
    },
    'prompt_eng': {
        'patterns': [r'Prompt', r'提示词', r'prompt engineering'],
        'weight': 1.0,
        'label': 'Prompt工程'
    },
    'badcase': {
        'patterns': [r'[Bb]ad\s*[Cc]ase', r'坏案例', r'问题归因'],
        'weight': 1.0,
        'label': 'Badcase分析'
    },
    'product_mgmt': {
        'patterns': [r'产品经理', r'PRD', r'产品规划', r'产品设计'],
        'weight': 1.0,
        'label': '产品管理(高阶管理岗加分)'
    },
}

NEGATIVE_KEYWORDS = {
    'pure_management': {
        'patterns': [r'团队管理', r'管理团队', r'带团队'],
        'weight': -1.5,
        'label': '纯管理背景(无一线经验时扣分)'
    },
    'pure_ops': {
        'patterns': [r'直播运营', r'GMV', r'货盘', r'供应链运营', r'采购', r'采销', r'销售额', r'带货'],
        'weight': -1.5,
        'label': '纯运营/直播/GMV/采销导向'
    },
    'pure_customer_service': {
        'patterns': [r'客服专员', r'售后客服', r'电话客服'],
        'weight': -0.5,
        'label': '纯客服背景(无评测转化时扣分)'
    },
    'non_ecom_annotation': {
        'patterns': [r'人脸检测', r'人脸识别', r'语音转写', r'语音标注', r'古文', r'古籍', r'医疗影像'],
        'weight': -1.5,
        'label': '非电商场景标注(领域不匹配)'
    },
}

EDUCATION_SCORES = {
    '硕士': 2.0,
    '研究生': 2.0,
    'MBA': 1.5,
    '本科': 1.0,
    '大专': 0.5,
}

def extract_text(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text.strip()

def clean_text(text):
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        if len(line) <= 2:
            continue
        if re.match(r'^[A-Za-z0-9~_\-]+$', line) and len(line) < 20:
            continue
        cleaned.append(line)
    return ' '.join(cleaned)

def score_resume(text, position_type='执行'):
    cleaned = clean_text(text)

    positive_signals = []
    negative_signals = []
    score = 0.0

    # Education
    edu_found = None
    for edu, edu_score in EDUCATION_SCORES.items():
        if edu in cleaned:
            if edu_found is None or edu_score > EDUCATION_SCORES.get(edu_found, 0):
                edu_found = edu
    if edu_found:
        score += EDUCATION_SCORES[edu_found]
        positive_signals.append(f"学历: {edu_found} (+{EDUCATION_SCORES[edu_found]})")

    # Positive keywords
    for key, info in POSITIVE_KEYWORDS.items():
        for pattern in info['patterns']:
            if re.search(pattern, cleaned, re.I):
                score += info['weight']
                positive_signals.append(f"{info['label']} (+{info['weight']})")
                break

    # Negative keywords (context-dependent)
    for key, info in NEGATIVE_KEYWORDS.items():
        for pattern in info['patterns']:
            if re.search(pattern, cleaned, re.I):
                if key == 'pure_management' and position_type in ['高阶管理', '组长']:
                    positive_signals.append(f"管理经验(对{position_type}岗加分) (+1.0)")
                    score += 1.0
                elif key == 'pure_customer_service':
                    has_eval = any('评测' in s or '标注' in s for s in positive_signals)
                    if not has_eval:
                        score += info['weight']
                        negative_signals.append(f"{info['label']} ({info['weight']})")
                elif key == 'non_ecom_annotation':
                    has_ecom = any('电商' in s for s in positive_signals)
                    if not has_ecom:
                        score += info['weight']
                        negative_signals.append(f"{info['label']} ({info['weight']})")
                elif key == 'pure_ops':
                    has_eval = any('评测' in s or '标注' in s for s in positive_signals)
                    if not has_eval:
                        score += info['weight']
                        negative_signals.append(f"{info['label']} ({info['weight']})")
                else:
                    has_user = any('用户视角' in s for s in positive_signals)
                    if not has_user:
                        score += info['weight']
                        negative_signals.append(f"{info['label']} ({info['weight']})")
                break

    # Position-specific adjustments
    if position_type == '食品生鲜':
        if re.search(r'食品|生鲜|餐饮|美食', cleaned):
            score += 2.0
            positive_signals.append("食品生鲜行业经验 (+2.0)")
        else:
            score -= 3.0
            negative_signals.append("无食品生鲜行业经验 (-3.0)")

    if position_type == '组长':
        if re.search(r'带.*?团队|管理.*?\d+人|组长|主管', cleaned):
            score += 1.5
            positive_signals.append("团队管理经验 (+1.5)")
        else:
            score -= 1.5
            negative_signals.append("无带队经验 (-1.5)")

    # === 业务深度信号检测 ===
    has_ai = any('AI' in s or '标注' in s or '评测' in s or 'Prompt' in s for s in positive_signals)

    biz_depth_score = 0
    biz_signals = []

    year_matches = re.findall(r'(\d{4})\s*[-–.]\s*(\d{4}|至今|present)', cleaned, re.I)
    if len(year_matches) >= 2:
        biz_depth_score += 1.0
        biz_signals.append("多段工作经历")

    if re.search(r'品类运营|商品运营|品类管理|选品策略|SKU|商品生命周期', cleaned):
        biz_depth_score += 1.5
        biz_signals.append("电商品类运营深度")

    platform_count = sum(1 for p in ['盒马', '天猫', '淘宝', '京东', '拼多多', '抖音', '快手', '美团', '饿了么', '叮咚', '得物', '小红书'] if p in cleaned)
    category_count = sum(1 for c in ['水果', '蔬菜', '生鲜', '美妆', '服装', '家居', '3C', '数码', '食品', '母婴', '户外', '快消', '家装', '烘焙', '冷藏'] if c in cleaned)
    if platform_count >= 2 or category_count >= 3:
        biz_depth_score += 1.5
        biz_signals.append(f"多平台/多品类覆盖(平台{platform_count}个,品类{category_count}个)")

    if re.search(r'数据分析|数据驱动|看板|转化率|复购率|环比|同比', cleaned):
        biz_depth_score += 1.0
        biz_signals.append("数据驱动/分析能力")

    # === 按岗位类型差异化应用业务深度 ===
    if biz_depth_score >= 2.0:
        if position_type == '食品生鲜':
            # 行业知识型岗位：业务深度完全补偿AI缺失
            if not has_ai:
                score += biz_depth_score
                positive_signals.append(f"行业深度补偿AI缺失(行业知识型岗位) (+{biz_depth_score}): {', '.join(biz_signals)}")
            else:
                bonus = biz_depth_score * 0.5
                score += bonus
                positive_signals.append(f"行业深度+AI双优 (+{bonus}): {', '.join(biz_signals)}")
        elif position_type == '执行':
            # 执行岗：业务深度是加分项，但补偿力度减半
            bonus = biz_depth_score * 0.5 if not has_ai else biz_depth_score * 0.3
            score += bonus
            positive_signals.append(f"业务深度加分(执行岗) (+{bonus:.1f}): {', '.join(biz_signals)}")
        else:
            # 高阶管理/组长：业务深度仅作为小幅加分，不能替代AI理解
            bonus = biz_depth_score * 0.3
            score += bonus
            positive_signals.append(f"业务深度加分(需同时具备AI理解) (+{bonus:.1f}): {', '.join(biz_signals)}")
            if not has_ai:
                negative_signals.append("高阶管理/组长岗缺少AI理解(业务深度无法替代)")

    # 有AI但无用户视角 → 所有岗位的风险信号
    if has_ai and not any('用户视角' in s for s in positive_signals):
        negative_signals.append("有AI经验但缺用户视角(面试高淘汰风险)")

    # 商品导购场景理解（面试最核心维度）
    if re.search(r'导购|商品推荐|购物|选品|挑选|网购|消费者', cleaned):
        score += 1.0
        positive_signals.append("商品导购/购物场景理解 (+1.0)")
    elif position_type in ['执行', '组长']:
        negative_signals.append("未体现商品导购场景理解(面试重点考察)")

    # Normalize to 1-10 scale
    raw_max = 20.0
    normalized = max(1, min(10, int(score / raw_max * 10 + 3)))

    # Decision
    if position_type == '执行':
        threshold = 5
    elif position_type == '组长':
        threshold = 6
    elif position_type == '高阶管理':
        threshold = 6
    else:  # 食品生鲜
        threshold = 6

    decision = '通过' if normalized >= threshold else '不通过'

    return {
        'score': normalized,
        'raw_score': round(score, 1),
        'decision': decision,
        'positive_signals': positive_signals,
        'negative_signals': negative_signals,
        'position_type': position_type,
    }

def main():
    parser = argparse.ArgumentParser(description='Score a resume PDF')
    parser.add_argument('pdf_path', help='Path to PDF file')
    parser.add_argument('--position', default='执行',
                       choices=['执行', '组长', '高阶管理', '食品生鲜'],
                       help='Position type (default: 执行)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()

    text = extract_text(args.pdf_path)
    result = score_resume(text, args.position)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        icon = '✅' if result['decision'] == '通过' else '❌'
        print(f"\n{'='*50}")
        print(f"评估结论: {icon} 建议{result['decision']}")
        print(f"匹配度评分: {result['score']}/10 (原始分: {result['raw_score']})")
        print(f"目标岗位类型: {result['position_type']}")
        print(f"{'='*50}")
        print(f"\n正面信号:")
        for s in result['positive_signals']:
            print(f"  ✓ {s}")
        print(f"\n风险信号:")
        for s in result['negative_signals']:
            print(f"  ✗ {s}")
        if not result['negative_signals']:
            print(f"  (无明显风险信号)")

if __name__ == '__main__':
    main()
