import os
import pandas as pd
from langchain_text_splitters import MarkdownHeaderTextSplitter

# =========================
# 1. doc映射
# =========================

doc_map = {
    "about.md": "DOC001",
    "welcome_pack.md": "DOC002",
    "taking_holiday.md": "DOC003",
    "flexible_working.md": "DOC004",
    "cycle_to_work_scheme.md": "DOC005",
    "hybrid_working.md": "DOC006",
    "help_to_buy_tech.md": "DOC007",
    "income_protection_and_life_insurance.md": "DOC008",
    "lunchers.md": "DOC009",
    "pension_scheme.md": "DOC010",
    "private_medical_insurance.md": "DOC011",
    "season_ticket_loan.md": "DOC012",
    "Unum_Help_at_hand.md": "DOC013",
    "work_ready.md": "DOC014",
    "associate_business_analyst.md": "DOC015",
    "associate_designer.md": "DOC016",
    "associate_product_manager.md": "DOC017",
    "associate_software_engineer.md": "DOC018",
    "delivery_director.md": "DOC019",
    "finance_business_partner.md": "DOC020",
    "head_of_service_line.md": "DOC021",
    "lead_business_analyst.md": "DOC022",
    "lead_data_engineer.md": "DOC023"
}

# =========================
# 2. 增强分类（STEP1关键新增）
# =========================

doc_type_map = {
    "DOC001":"company",
    "DOC002":"company",
    "DOC003":"benefits",
    "DOC004":"benefits",
    "DOC005":"benefits",
    "DOC006":"benefits",
    "DOC007":"benefits",
    "DOC008":"benefits",
    "DOC009":"benefits",
    "DOC010":"benefits",
    "DOC011":"benefits",
    "DOC012":"benefits",
    "DOC013":"benefits",
    "DOC014":"benefits",
    "DOC015":"roles",
    "DOC016":"roles",
    "DOC017":"roles",
    "DOC018":"roles",
    "DOC019":"roles",
    "DOC020":"roles",
    "DOC021":"roles",
    "DOC022":"roles",
    "DOC023":"roles"
}

# =========================
# 3. Markdown splitter
# =========================

headers_to_split_on = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3")
]

splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=headers_to_split_on
)

# =========================
# 4. 遍历文件
# =========================

root_dir = "./"

md_files = []

for root, _, files in os.walk(root_dir):
    for file in files:
        if file.endswith(".md"):
            md_files.append(os.path.join(root, file))

print(f"发现 {len(md_files)} 个Markdown文件")

# =========================
# 5. chunk生成
# =========================

rows = []
chunk_counter = 1

for filepath in md_files:

    filename = os.path.basename(filepath)

    if filename not in doc_map:
        print(f"[跳过] 未登记文件: {filename}")
        continue

    doc_id = doc_map[filename]
    source_type = doc_type_map.get(doc_id, "unknown")

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        docs = splitter.split_text(text)

        for doc in docs:

            content = doc.page_content.strip()

            if not content:
                continue

            rows.append({
                "chunk_id": f"CH{chunk_counter:04d}",
                "doc_id": doc_id,
                "file_name": filename,

                # ======================
                # ⭐ STEP1增强字段
                # ======================
                "source_type": source_type,
                "doc_title": filename.replace(".md", ""),
                "h1": doc.metadata.get("h1", ""),
                "h2": doc.metadata.get("h2", ""),
                "h3": doc.metadata.get("h3", ""),
                "section_path": " > ".join([
                    doc.metadata.get("h1", ""),
                    doc.metadata.get("h2", ""),
                    doc.metadata.get("h3", "")
                ]).strip(" >"),

                "text": content
            })

            chunk_counter += 1

    except Exception as e:
        print(f"[错误] {filename}: {e}")

# =========================
# 6. 导出增强版数据
# =========================

df = pd.DataFrame(rows)

df.to_csv(
    "chunks_enhanced.csv",
    index=False,
    encoding="utf-8-sig"
)

print("=" * 50)
print(f"生成完成")
print(f"总Chunk数: {len(df)}")
print("输出文件: chunks_enhanced.csv")
print("=" * 50)

print(df.head())