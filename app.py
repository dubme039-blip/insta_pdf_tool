# app.py
import os
import io
import zipfile
from typing import List, Tuple
from PIL import Image, ImageEnhance, ImageDraw, ImageFont, ImageOps
import streamlit as st

# optional OpenAI usage
try:
    import openai
    HAS_OPENAI = True
except Exception:
    HAS_OPENAI = False

# ---------- Config ----------
OUTPUT_WIDTH = 1080   # Instagram recommended width for portrait
OUTPUT_HEIGHT = 1350  # Instagram portrait 4:5 -> 1080x1350
MAX_PRODUCT_IMAGES = 10
ASSETS_DIR = "assets"
DEFAULT_FONT_PATH = os.path.join(ASSETS_DIR, "NotoSerifJP-Regular.ttf")  # place a Japanese-capable font here
FALLBACK_FONT_SIZE_TITLE = 56
FALLBACK_FONT_SIZE_HEADER = 34
FALLBACK_FONT_SIZE_FOOTER = 30

# ---------- Helpers ----------
def load_font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size=size)
    except Exception:
        return ImageFont.load_default()

def darken_image(img: Image.Image, amount: float = 0.6) -> Image.Image:
    """暗めに調整。amount=0.6 は 60% 明るさ（やや暗め）。"""
    enhancer = ImageEnhance.Brightness(img.convert("RGB"))
    return enhancer.enhance(amount)

def paste_center(dst: Image.Image, src: Image.Image, box=None):
    """中央に配置して貼る（オプションの box が与えられればその中で中央合わせ）"""
    if box:
        x0, y0, x1, y1 = box
        w_box = x1 - x0
        h_box = y1 - y0
        src = src.copy()
        src.thumbnail((w_box, h_box), Image.LANCZOS)
        x = x0 + (w_box - src.width)//2
        y = y0 + (h_box - src.height)//2
        dst.paste(src, (x, y), mask=src if src.mode == "RGBA" else None)
    else:
        x = (dst.width - src.width)//2
        y = (dst.height - src.height)//2
        dst.paste(src, (x, y), mask=src if src.mode == "RGBA" else None)

def multiline_text_centered(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, box: Tuple[int,int,int,int], fill=(255,255,255), spacing=4):
    """与えた矩形(box)内にテキストを中央寄せで描画（改行を調整）"""
    x0,y0,x1,y1 = box
    max_w = x1 - x0
    max_h = y1 - y0
    # try different wrapping by splitting lines
    lines = text.split("\n")
    # compute total height
    line_heights = [font.getbbox(line)[3] - font.getbbox(line)[1] for line in lines]
    total_h = sum(line_heights) + spacing*(len(lines)-1)
    start_y = y0 + (max_h - total_h)//2
    for i, line in enumerate(lines):
        w = font.getbbox(line)[2] - font.getbbox(line)[0]
        x = x0 + (max_w - w)//2
        y = start_y + sum(line_heights[:i]) + i*spacing
        draw.text((x,y), line, font=font, fill=fill)

def auto_layout_product_images(images: List[Image.Image], canvas_w: int, canvas_h: int, margin=60) -> Image.Image:
    """
    商品ページ本文の自動レイアウト。
    画像枚数に合わせて縦横比を考慮しつつグリッド化。
    返すのは本文領域 (canvas_w x canvas_h) に配置された Image。
    """
    n = len(images)
    out = Image.new("RGB", (canvas_w, canvas_h), (255,255,255))
    # choose grid
    if n == 1:
        img = images[0].copy()
        img.thumbnail((canvas_w - 2*margin, canvas_h - 2*margin), Image.LANCZOS)
        paste_center(out, img)
    elif n == 2:
        w = (canvas_w - 3*margin) // 2
        h = canvas_h - 2*margin
        for i,img in enumerate(images[:2]):
            im = img.copy()
            im.thumbnail((w, h), Image.LANCZOS)
            x = margin + i*(w + margin)
            y = (canvas_h - im.height)//2
            out.paste(im, (x,y), mask=im if im.mode=="RGBA" else None)
    elif n <= 4:
        cols = 2
        rows = (n+1)//2
        cell_w = (canvas_w - (cols+1)*margin)//cols
        cell_h = (canvas_h - (rows+1)*margin)//rows
        idx=0
        for r in range(rows):
            for c in range(cols):
                if idx>=n: break
                img = images[idx].copy()
                img.thumbnail((cell_w, cell_h), Image.LANCZOS)
                x = margin + c*(cell_w + margin) + (cell_w - img.width)//2
                y = margin + r*(cell_h + margin) + (cell_h - img.height)//2
                out.paste(img, (x,y), mask=img if img.mode=="RGBA" else None)
                idx+=1
    else:
        # 5~10: make 3 columns layout
        cols = 3
        rows = (n + cols - 1)//cols
        cell_w = (canvas_w - (cols+1)*margin)//cols
        cell_h = (canvas_h - (rows+1)*margin)//rows
        idx=0
        for r in range(rows):
            for c in range(cols):
                if idx>=n: break
                img = images[idx].copy()
                img.thumbnail((cell_w, cell_h), Image.LANCZOS)
                x = margin + c*(cell_w + margin) + (cell_w - img.width)//2
                y = margin + r*(cell_h + margin) + (cell_h - img.height)//2
                out.paste(img, (x,y), mask=img if img.mode=="RGBA" else None)
                idx+=1
    return out

# ---------- Copy generation ----------
def generate_copy_options_with_openai(product_name: str, cover_instruction: str = "", tone: str = "高級志向で静かな贅沢を感じさせる日本語") -> Tuple[List[str], List[str]]:
    """
    OpenAIが使える場合に3案ずつ生成する関数。
    戻り値: (title_options, footer_options)
    """
    if not HAS_OPENAI:
        raise RuntimeError("OpenAIライブラリがありません。")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY が環境変数に設定されていません。")
    openai.api_key = api_key

    system = (
        "あなたは高級家具ブランドのコピーライターです。"
        "出力は必ず日本語で、過度な煽りを避け、落ち着いた上質なトーンで記述してください。"
    )
    prompt = (
        f"商品名: {product_name}\n"
        f"表紙用補足: {cover_instruction}\n"
        f"トーン: {tone}\n\n"
        "以下を生成してください：\n"
        "1) 表紙タイトルの候補を日本語で3つ（各案は短め、1〜6語程度、ラグジュアリーで静かな余白感）\n"
        "2) フッター用の短い商品紹介文（高級志向／キャッチー・シンプル）を日本語で3つ（各案は1行/短文）\n"
        "出力は JSON 配列として、{\"titles\": [..], \"footers\": [..]} の形式で答えてください。"
    )
    # Chat completion
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system", "content": system},
            {"role":"user", "content": prompt}
        ],
        max_tokens=400,
        temperature=0.8,
    )
    text = resp["choices"][0]["message"]["content"]
    # try to parse JSON from response leniently
    import json, re
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        j = json.loads(m.group(0))
        titles = j.get("titles", [])[:3]
        footers = j.get("footers", [])[:3]
        return titles, footers
    else:
        # fallback: naive split by lines
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        titles = lines[:3]
        footers = lines[3:6] if len(lines)>=6 else lines[3:3+3]
        return titles, footers

def generate_copy_options_local(product_name: str) -> Tuple[List[str], List[str]]:
    """
    OpenAIが使えない場合のフォールバック生成（日本語：高級トーン）。
    """
    # small local template set
    titles_templates = [
        f"{product_name} — 静かな佇まい",
        f"洗練された日常、{product_name}",
        f"{product_name} | 余白を纏うデザイン",
        f"時を重ねる、{product_name}",
        f"{product_name} — 穏やかな上質"
    ]
    footers_templates = [
        f"{product_name}。上質な素材と静かな存在感が、暮らしに深みをもたらす。",
        f"{product_name}。細部まで丁寧に仕立てられた、永く寄り添う佇まい。",
        f"{product_name}。穏やかな美しさを、日々の風景に。",
        f"{product_name}。控えめで確かな存在感。",
        f"{product_name}。あなたの空間に静かな品を添える一品。"
    ]
    return titles_templates[:3], footers_templates[:3]

# ---------- Image generation pipeline ----------
def make_cover_image(cover_img: Image.Image, title: str, font_path: str = DEFAULT_FONT_PATH) -> Image.Image:
    canvas = Image.new("RGB", (OUTPUT_WIDTH, OUTPUT_HEIGHT), (255,255,255))
    # fit cover image to canvas and darken
    cover = cover_img.copy().convert("RGB")
    cover = ImageOps.fit(cover, (OUTPUT_WIDTH, OUTPUT_HEIGHT), Image.LANCZOS)
    cover = darken_image(cover, amount=0.55)  # やや暗め
    canvas.paste(cover, (0,0))
    draw = ImageDraw.Draw(canvas)
    # title text: large, centered, white
    title_font = load_font(font_path, 72)
    # draw subtle shadow for readability
    w = title_font.getbbox(title)[2] - title_font.getbbox(title)[0]
    x = (OUTPUT_WIDTH - w)//2
    y = int(OUTPUT_HEIGHT * 0.2)
    # shadow
    draw.text((x+2,y+2), title, font=title_font, fill=(0,0,0,200))
    draw.text((x,y), title, font=title_font, fill=(255,255,255))
    return canvas

def make_product_page(cover_title: str, product_name: str, product_images: List[Image.Image], footer_text: str, font_path: str = DEFAULT_FONT_PATH) -> Image.Image:
    canvas = Image.new("RGB", (OUTPUT_WIDTH, OUTPUT_HEIGHT), (255,255,255))
    draw = ImageDraw.Draw(canvas)
    # Header area (top) — small band
    header_h = 160
    header_bg = Image.new("RGB", (OUTPUT_WIDTH, header_h), (245,245,245))
    canvas.paste(header_bg, (0,0))
    header_font = load_font(font_path, 28)
    # Draw cover title and product name
    header_text = f"{cover_title}  —  {product_name}"
    draw.text((60, 40), header_text, font=header_font, fill=(30,30,30))
    # Body area - between header and footer
    footer_h = 160
    body_h = OUTPUT_HEIGHT - header_h - footer_h
    body_box = (0, header_h, OUTPUT_WIDTH, header_h + body_h)
    # prepare product images (resize/layout)
    # convert uploaded images into PIL with safe mode
    prepared_imgs = []
    for im in product_images:
        if im.mode not in ("RGB","RGBA"):
            im = im.convert("RGB")
        prepared_imgs.append(im)
    body_img = auto_layout_product_images(prepared_imgs, OUTPUT_WIDTH, body_h, margin=48)
    canvas.paste(body_img, (0, header_h))
    # Footer area
    footer_bg = Image.new("RGB", (OUTPUT_WIDTH, footer_h), (245,245,245))
    canvas.paste(footer_bg, (0, OUTPUT_HEIGHT-footer_h))
    footer_font = load_font(font_path, 28)
    # Draw footer text centered vertically in footer band
    bbox = footer_font.getbbox(footer_text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (OUTPUT_WIDTH - text_w)//2
    y = OUTPUT_HEIGHT - footer_h + (footer_h - text_h)//2
    draw.text((x,y), footer_text, font=footer_font, fill=(40,40,40))
    return canvas

def make_end_page(template_img: Image.Image = None, font_path: str = DEFAULT_FONT_PATH) -> Image.Image:
    # If user provided a custom end/back image, we can use it; else create a minimal one
    if template_img:
        out = ImageOps.fit(template_img, (OUTPUT_WIDTH, OUTPUT_HEIGHT), Image.LANCZOS)
        return out
    else:
        canvas = Image.new("RGB", (OUTPUT_WIDTH, OUTPUT_HEIGHT), (20,20,20))
        draw = ImageDraw.Draw(canvas)
        font = load_font(font_path, 28)
        draw.text((60, OUTPUT_HEIGHT//2 - 20), "DESIGN FOR YOUR LIFE", font=font, fill=(255,255,255))
        return canvas

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Instagram 高級ポスト自動生成ツール", layout="centered")
st.title("📱 Instagram 投稿自動生成（高級志向・日本語）")
st.markdown(
    """
    このツールは、あなたがアップロードした**表紙画像** + **商品名** + **商品画像（1〜10枚）**から
    「表紙 / 商品紹介 / 裏表紙」の3枚セットを自動生成します。\n
    - 表紙はやや暗めに調整してタイトルを載せます。  
    - 商品ページはヘッダー（表紙タイトル＋商品名）/ 本文（画像のみ）/ フッター（高級トーンの短文）で構成。  
    - 全て日本語・高級トーンで統一。  
    """
)

with st.sidebar:
    st.header("設定")
    st.write("出力は Instagram 縦 1080×1350 を想定しています（iPhone でそのまま投稿しやすい比率）。")
    st.write(f"最大商品画像数: {MAX_PRODUCT_IMAGES}")
    use_openai = st.checkbox("OpenAIでキャプション生成（環境変数 OPENAI_API_KEY が必要）", value=False)
    font_upload = st.file_uploader("カスタムフォント（日本語対応）を入れる（任意）", type=["ttf","otf"])
    if font_upload:
        os.makedirs(ASSETS_DIR, exist_ok=True)
        font_path = os.path.join(ASSETS_DIR, font_upload.name)
        with open(font_path, "wb") as f:
            f.write(font_upload.getbuffer())
        st.success(f"フォントを保存しました: {font_path}")
    st.caption("※フォントファイルは Noto Serif JP 等の日本語対応フォントを推奨します。")

# Main inputs
st.subheader("1) 画像アップロードと商品情報")
cover_file = st.file_uploader("表紙用画像（1枚） — 明るさは自動でやや暗めに調整されます", type=["png","jpg","jpeg"])
product_name = st.text_input("商品名（日本語推奨）")
uploaded_images = st.file_uploader(f"商品画像（1〜{MAX_PRODUCT_IMAGES}枚）", type=["png","jpg","jpeg"], accept_multiple_files=True)

if uploaded_images:
    if len(uploaded_images) > MAX_PRODUCT_IMAGES:
        st.error(f"最大 {MAX_PRODUCT_IMAGES} 枚までです。不要なファイルは外してください。")

generate_btn = st.button("① 案を生成して表示（タイトル3案・フッター3案）")

titles = []
footers = []

if generate_btn:
    if not product_name or not cover_file or not uploaded_images:
        st.error("表紙画像・商品名・商品画像をすべてアップしてください。")
    else:
        # load images
        cover_img = Image.open(cover_file).convert("RGB")
        prod_imgs = [Image.open(f).convert("RGB") for f in uploaded_images[:MAX_PRODUCT_IMAGES]]
        st.info("コピー案を生成中…（OpenAI利用はサーバー環境とAPIキーが必要）")
        try:
            if use_openai and HAS_OPENAI and os.environ.get("OPENAI_API_KEY"):
                titles, footers = generate_copy_options_with_openai(product_name)
            else:
                titles, footers = generate_copy_options_local(product_name)
            # show options
            st.success("案を作成しました。下から選んでください。")
            st.subheader("表紙タイトル（3案）")
            title_choice = st.radio("表紙タイトルを選択", titles, index=0, key="title_radio")
            st.subheader("フッター（商品紹介文） — 3案")
            footer_choice = st.radio("フッター文を選択", footers, index=0, key="footer_radio")
            st.markdown("----")
            st.write("選んだ案で画像を生成します。")
            # preview small
            st.image(cover_img, caption="アップロード表紙画像（元）", use_column_width=True)
        except Exception as e:
            st.error(f"エラー: {e}")
            titles, footers = generate_copy_options_local(product_name)
            st.warning("フォールバック案を生成しました。")
            title_choice = st.radio("表紙タイトルを選択", titles, index=0, key="title_radio_fallback")
            footer_choice = st.radio("フッター文を選択", footers, index=0, key="footer_radio_fallback")

        # button to make images
        if st.button("② 選択案で最終画像を生成する"):
            # generate final images
            st.info("画像を生成中…")
            # load chosen font path
            font_path = DEFAULT_FONT_PATH
            if os.path.exists(DEFAULT_FONT_PATH):
                font_path = DEFAULT_FONT_PATH
            else:
                # if user uploaded font via sidebar, use it
                user_fonts = [os.path.join(ASSETS_DIR, f) for f in os.listdir(ASSETS_DIR)] if os.path.exists(ASSETS_DIR) else []
                if user_fonts:
                    font_path = user_fonts[0]
            cover_out = make_cover_image(cover_img, title_choice, font_path=font_path)
            product_out = make_product_page(title_choice, product_name, prod_imgs, footer_choice, font_path=font_path)
            # end page: reuse cover darkened or minimal
            end_out = make_end_page(template_img=None, font_path=font_path)

            # show previews
            st.subheader("生成プレビュー")
            st.image(cover_out, caption="表紙（出力）", use_column_width=True)
            st.image(product_out, caption="商品紹介ページ（出力）", use_column_width=True)
            st.image(end_out, caption="裏表紙（出力）", use_column_width=True)

            # prepare zip
            bio = io.BytesIO()
            with zipfile.ZipFile(bio, mode="w") as z:
                for name, img in [("cover.png", cover_out), ("product.png", product_out), ("end.png", end_out)]:
                    buf = io.BytesIO()
                    img.save(buf, format="PNG", optimize=True)
                    z.writestr(name, buf.getvalue())
            bio.seek(0)
            st.success("生成が完了しました。ダウンロードしてください。")
            st.download_button("画像3枚を ZIP でダウンロード", data=bio, file_name=f"{product_name}_instagram_post.zip", mime="application/zip")
