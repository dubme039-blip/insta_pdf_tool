import streamlit as st
from PIL import Image
from fpdf import FPDF
import io
import tempfile
from openai import OpenAI

client = OpenAI()

# 日本語フォント（ipaexg.ttf）を利用
FONT_PATH = "ipaexg.ttf"

st.set_page_config(page_title="Instagram投稿作成ツール", layout="wide")
st.title("📸 Instagram投稿作成ツール（iPhone対応）")

# ------------------------------
# ステップ1: 表紙画像アップロード
# ------------------------------
st.header("ステップ1: 表紙画像アップアップ（任意）")
cover_file = st.file_uploader(
    "表紙として使う画像をアップロード（任意）",
    type=["png", "jpg", "jpeg"]
)

# ------------------------------
# ステップ2: 商品画像アップロード
# ------------------------------
st.header("ステップ2: 商品画像アップロード")
uploaded_files = st.file_uploader(
    "最大4枚までアップロードできます",
    accept_multiple_files=True,
    type=["png", "jpg", "jpeg"]
)

# ------------------------------
# ステップ3: 商品タイトル入力
# ------------------------------
titles = []
if uploaded_files:
    st.header("ステップ3: 商品タイトル入力")
    for file in uploaded_files:
        title = st.text_input(f"{file.name} の商品名")
        titles.append(title)

# ------------------------------
# ステップ4: 商品説明文生成
# ------------------------------
st.header("ステップ4: 商品説明文をAIで生成")
descriptions = []

for idx, title in enumerate(titles):
    if title:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": f"商品名「{title}」の短い紹介文を3つ作ってください。"
                }
            ],
            max_tokens=100
        )

        options = [
            line for line in response.choices[0].message.content.split("\n")
            if line.strip()
        ]

        selected = st.selectbox(f"{title} の紹介文を選択", options, key=f"desc_{idx}")
        descriptions.append(selected)
    else:
        descriptions.append("")

# ------------------------------
# ステップ5: PDF生成
# ------------------------------
st.header("ステップ5: PDF生成")
if st.button("PDF生成"):
    pdf = FPDF()
    pdf.add_page()

    # 日本語フォント登録
    pdf.add_font("JP", "", FONT_PATH, uni=True)
    pdf.set_font("JP", "", 20)

    # ▼ 表紙ページ ▼
    if cover_file:
        img = Image.open(cover_file)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            cover_path = tmp.name
            img.save(cover_path)
        pdf.image(cover_path, x=10, y=10, w=pdf.w - 20)

    # 表紙タイトル
    pdf.set_y(pdf.h - 40)
    pdf.multi_cell(0, 10, "表紙タイトル")

    # ▼ 商品ページ ▼
    for idx, file in enumerate(uploaded_files):
        img = Image.open(file)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img_path = tmp.name
            img.save(img_path)

        pdf.add_page()
        pdf.image(img_path, x=10, y=10, w=pdf.w - 20)

        # タイトル
        pdf.set_y(pdf.h - 40)
        pdf.set_font("JP", "", 16)
        pdf.multi_cell(0, 10, titles[idx])

        # 説明文
        pdf.set_font("JP", "", 12)
        pdf.multi_cell(0, 10, descriptions[idx])

    # PDFをバッファで生成
    pdf_buffer = io.BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)

    st.success("PDF生成が完了しました！📄")
    st.download_button(
        "PDFをダウンロード",
        pdf_buffer,
        file_name="insta_post.pdf",
        mime="application/pdf"
    )
