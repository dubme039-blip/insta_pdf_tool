import streamlit as st
from PIL import Image
from fpdf import FPDF
import io
import tempfile
from openai import OpenAI

client = OpenAI()

st.set_page_config(page_title="Instagram投稿作成ツール", layout="wide")
st.title("📸 Instagram投稿作成ツール（iPhone対応）")

# ------------------------------
# ステップ1: 表紙画像アップロード
# ------------------------------
st.header("ステップ1: 表紙画像（任意）アップロード")
cover_file = st.file_uploader(
    "表紙として使う画像を1枚アップロードしてください（必須ではありません）",
    type=['png','jpg','jpeg'],
    accept_multiple_files=False
)

# ------------------------------
# ステップ2: 商品画像アップロード
# ------------------------------
st.header("ステップ2: 商品画像アップロード")
uploaded_files = st.file_uploader(
    "最大4枚までアップロード",
    accept_multiple_files=True,
    type=['png','jpg','jpeg']
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
# ステップ4: 商品説明生成
# ------------------------------
st.header("ステップ4: 商品説明生成")
descriptions = []

for idx, title in enumerate(titles):
    if title:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": f"商品名「{title}」の短い紹介文を3つ作ってください"}
            ],
            max_tokens=80
        )

        options = [
            line for line in response.choices[0].message.content.split('\n')
            if line.strip()
        ]

        selected = st.selectbox(f"{title} の紹介文を選択", options, key=idx)
        descriptions.append(selected)
    else:
        descriptions.append("")

# ------------------------------
# ステップ5: PDF生成
# ------------------------------
st.header("ステップ5: PDF生成")
if st.button("PDF生成"):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ▼ 表紙ページ ▼
    pdf.add_page()

    if cover_file:
        img = Image.open(cover_file)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            cover_path = tmp.name
            img.save(cover_path)
        pdf.image(cover_path, x=10, y=10, w=pdf.w-20)

    pdf.set_y(pdf.h - 40)
    pdf.set_font("Arial", "B", 20)
    pdf.multi_cell(0, 10, "表紙タイトル")

    # ▼ 商品ページ ▼
    for idx, file in enumerate(uploaded_files):
        img = Image.open(file)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img_path = tmp.name
            img.save(img_path)

        pdf.add_page()
        pdf.image(img_path, x=10, y=10, w=pdf.w-20)

        pdf.set_y(pdf.h - 40)
        pdf.set_font("Arial", "B", 14)
        pdf.multi_cell(0, 10, titles[idx])

        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, descriptions[idx])

    # PDF生成
    pdf_buffer = io.BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)

    st.success("PDF生成完了！")
    st.download_button(
        "PDFをダウンロード",
        pdf_buffer,
        file_name="insta_post.pdf",
        mime="application/pdf"
    )
