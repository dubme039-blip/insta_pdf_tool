import streamlit as st
from PIL import Image
from fpdf import FPDF
import io
import tempfile
import requests
import base64
from openai import OpenAI

client = OpenAI()

st.set_page_config(page_title="Instagram投稿作成ツール", layout="wide")
st.title("📸 Instagram投稿作成ツール（iPhone対応）")

# ------------------------------
# ステップ1: 商品画像アップロード
# ------------------------------
st.header("ステップ1: 商品画像アップロード")
uploaded_files = st.file_uploader(
    "最大4枚までアップロード",
    accept_multiple_files=True,
    type=['png','jpg','jpeg']
)

# ------------------------------
# ステップ2: 商品タイトル入力
# ------------------------------
titles = []
if uploaded_files:
    st.header("ステップ2: 商品タイトル入力")
    for file in uploaded_files:
        title = st.text_input(f"{file.name} の商品名")
        titles.append(title)

# ------------------------------
# ステップ3: 表紙生成（DALL·E）
# ------------------------------
st.header("ステップ3: 表紙生成")
cover_image = None

if st.button("表紙を自動生成 (無料クレジット1枚分)"):
    if uploaded_files:
        prompt = f"これらの商品を紹介するインスタグラム風の表紙画像を作ってください: {[file.name for file in uploaded_files]}"
        try:
            response = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size="1024x1024"
            )
            image_base64 = response.data[0].b64_json
            image_bytes = base64.b64decode(image_base64)

            st.image(image_bytes, caption="自動生成表紙")
            st.success("表紙生成成功")

            cover_image = image_bytes
        except Exception as e:
            st.error(f"生成エラー: {e}")
    else:
        st.warning("まず商品画像をアップロードしてください")

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
            max_tokens=50
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

    # 表紙追加
    if cover_image:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
            with open(tmp_path, "wb") as f:
                f.write(cover_image)

        pdf.add_page()
        pdf.image(tmp_path, x=10, y=10, w=pdf.w-20)
        pdf.set_y(pdf.h - 40)
        pdf.set_font("Arial", "B", 16)
        pdf.multi_cell(0, 10, "表紙タイトル")

    # 商品ページ
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
    st.download_button("PDFをダウンロード", pdf_buffer, file_name="insta_post.pdf", mime="application/pdf")
