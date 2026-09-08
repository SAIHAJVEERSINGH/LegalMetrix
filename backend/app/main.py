import os
import shutil
import tempfile
import traceback

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .ai import process_ocr
from .compliance import run_compliance
from .hardening import harden_ai_result
from .ocr import extract_text


app = FastAPI(
    title="LegalMetrix",
    description="AI-assisted packaged commodity compliance screening system",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "name": "LegalMetrix",
        "status": "online",
        "pipeline": "OCR -> Groq AI -> Compliance Engine",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "ocr": "PaddleOCR",
        "ai": "Groq",
        "compliance": "deterministic",
    }


@app.post("/api/inspection")
async def inspection(files: list[UploadFile] = File(...)):

    if not files:
        raise HTTPException(
            status_code=400,
            detail="At least one image is required.",
        )

    if len(files) > 6:
        raise HTTPException(
            status_code=400,
            detail="Maximum 6 images allowed.",
        )

    temp_paths = []

    try:
        all_text = []

        for index, upload in enumerate(files):

            filename = upload.filename or f"image_{index + 1}.jpg"

            print(
                f"\n[OCR] Processing image "
                f"{index + 1}/{len(files)}: {filename}"
            )

            if not upload.content_type:
                raise HTTPException(
                    status_code=400,
                    detail=f"No content type detected for {filename}.",
                )

            if not upload.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=400,
                    detail=f"{filename} is not an image.",
                )

            # Always use a known-safe image extension.
            # Do NOT depend on the user's original filename.
            temp = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".jpg",
            )

            temp_path = temp.name
            temp.close()

            temp_paths.append(temp_path)

            with open(temp_path, "wb") as destination:
                shutil.copyfileobj(upload.file, destination)

            print(f"[OCR] Saved temporary image: {temp_path}")

            try:
                text = extract_text(temp_path)

            except Exception as ocr_error:
                print(
                    f"\n[OCR ERROR] Failed on image "
                    f"{index + 1}: {filename}"
                )
                traceback.print_exc()

                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"OCR failed on image {index + 1} "
                        f"({filename}): {ocr_error}"
                    ),
                )

            print(
                f"[OCR] Image {index + 1} extracted "
                f"{len(text)} characters"
            )

            if text.strip():
                all_text.append(
                    f"IMAGE {index + 1}\n{text.strip()}"
                )

        ocr_text = "\n\n".join(all_text).strip()

        if not ocr_text:
            raise HTTPException(
                status_code=422,
                detail="No readable text was detected in the uploaded image(s).",
            )

        print("\n[AI] Sending combined OCR text to Groq...")

        try:
            ai_result = process_ocr(ocr_text)

        except Exception as ai_error:
            print("\n[AI ERROR]")
            traceback.print_exc()

            raise HTTPException(
                status_code=502,
                detail=f"AI processing failed: {ai_error}",
            )

        print("[AI] Extraction completed.")

        # Deterministic post-processing after Groq.
        # This does not replace or override the compliance engine.
        print("[HARDENING] Validating evidence, duplicates and cross-image consistency...")
        try:
            ai_result = harden_ai_result(
                ai_result,
                ocr_text,
            )
        except Exception as hardening_error:
            print("\n[HARDENING ERROR]")
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"AI hardening failed: {hardening_error}",
            )

        print("[HARDENING] Validation completed.")

        print("[COMPLIANCE] Running deterministic rules...")

        try:
            compliance = run_compliance(ai_result)

        except Exception as compliance_error:
            print("\n[COMPLIANCE ERROR]")
            traceback.print_exc()

            raise HTTPException(
                status_code=500,
                detail=f"Compliance engine failed: {compliance_error}",
            )

        print("[COMPLIANCE] Analysis completed.")

        return {
            "success": True,
            "images_processed": len(files),
            "ocr_text": ocr_text,
            "ai": ai_result.model_dump(),
            "compliance": compliance.model_dump(),
        }

    except HTTPException:
        raise

    except Exception as exc:
        print("\n========== LEGALMETRIX ERROR ==========")
        traceback.print_exc()
        print("========================================\n")

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    finally:
        for path in temp_paths:
            try:
                os.remove(path)
            except OSError:
                pass


paths = {
    route.path
    for route in app.routes
    if hasattr(route, "path")
}

assert "/" in paths
assert "/health" in paths
assert "/api/inspection" in paths

