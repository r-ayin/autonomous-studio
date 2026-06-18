#!/usr/bin/env python3
"""Extract text from a PDF resume using pdfplumber."""
import sys, os, re

try:
    import pdfplumber
except ImportError:
    os.system("pip install pdfplumber --break-system-packages -q")
    import pdfplumber

def extract(path):
    with pdfplumber.open(path) as pdf:
        text = ""
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text.strip()

def is_garbled(text, threshold=0.15):
    if not text or len(text.strip()) < 50:
        return True
    non_space = re.findall(r'\S', text)
    if not non_space:
        return True
    chinese = re.findall(r'[\u4e00-\u9fff]', text)
    ratio = len(chinese) / len(non_space)
    keywords = ['经验', '工作', '学历', '大学', '公司', '项目', '负责', '毕业', '技能', '教育']
    return ratio < threshold and not any(k in text for k in keywords)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: extract_pdf.py <path_to_pdf>")
        sys.exit(1)
    text = extract(sys.argv[1])
    if is_garbled(text):
        print("[GARBLED] PDF文本加密或损坏，无法提取有效内容", file=sys.stderr)
        sys.exit(2)
    print(text)
