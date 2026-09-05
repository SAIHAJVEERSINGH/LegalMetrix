import os

# Disable oneDNN / MKLDNN before Paddle is imported.
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"

from paddleocr import PaddleOCR


_ocr = None


def get_ocr():
    global _ocr

    if _ocr is None:
        _ocr = PaddleOCR(
            lang="en",
            device="cpu",
            enable_mkldnn=False,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    return _ocr


def extract_text(image_path: str) -> str:
    ocr = get_ocr()

    result = ocr.predict(image_path)

    texts = []

    for page in result:
        data = getattr(page, "json", None)

        if callable(data):
            data = data()

        if not isinstance(data, dict):
            continue

        res = data.get("res", data)

        for text in res.get("rec_texts", []):
            if text and str(text).strip():
                texts.append(str(text).strip())

    return "\n".join(texts)
