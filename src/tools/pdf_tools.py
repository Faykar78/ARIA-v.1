"""
PDF Tools for ARIA
Comprehensive PDF operations: create, convert, extract images, merge.
Uses PyMuPDF (fitz) for reading/extracting and fpdf2 for creating.
"""
import os
import time
import fitz  # PyMuPDF


OUTPUT_DIR = os.path.expanduser("~/Documents/aria_pdfs")


def _ensure_dir(path=None):
    """Ensure output directory exists."""
    d = os.path.dirname(path) if path else OUTPUT_DIR
    os.makedirs(d or OUTPUT_DIR, exist_ok=True)


def create_pdf(text: str, title: str = "", filename: str = None) -> dict:
    """
    Create a PDF with text content.

    Args:
        text: Text content for the PDF
        title: Optional title/heading
        filename: Output filename (auto-generated if not provided)

    Returns:
        dict with success and file path
    """
    try:
        from fpdf import FPDF

        if not filename:
            clean = (title or "document").replace(" ", "_")[:30].lower()
            filename = f"{clean}_{int(time.time())}.pdf"

        _ensure_dir()
        output_path = os.path.join(OUTPUT_DIR, filename)

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        if title:
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, title, ln=True, align="C")
            pdf.ln(10)

        pdf.set_font("Arial", size=12)
        # Handle multi-line text
        for line in text.split("\n"):
            pdf.multi_cell(0, 8, line)

        pdf.output(output_path)
        return {"success": True, "path": output_path,
                "message": f"PDF created: {output_path}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def images_to_pdf(image_paths: list, filename: str = None, title: str = "") -> dict:
    """
    Convert one or more images into a PDF.

    Args:
        image_paths: List of image file paths
        filename: Output PDF filename
        title: Optional title for the PDF

    Returns:
        dict with success and file path
    """
    try:
        from fpdf import FPDF

        if not filename:
            filename = f"images_{int(time.time())}.pdf"

        _ensure_dir()
        output_path = os.path.join(OUTPUT_DIR, filename)

        pdf = FPDF()

        for img_path in image_paths:
            if not os.path.exists(img_path):
                continue
            pdf.add_page()
            # Fit image to page (A4 = 210x297mm, with margins)
            pdf.image(img_path, x=10, y=10, w=190)

        if title:
            pdf.set_font("Arial", "B", 14)

        pdf.output(output_path)
        return {"success": True, "path": output_path,
                "message": f"PDF created from {len(image_paths)} image(s): {output_path}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def pdf_to_images(pdf_path: str, output_dir: str = None, dpi: int = 200) -> dict:
    """
    Convert each page of a PDF to PNG images.

    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save images (default: same dir as PDF)
        dpi: Resolution (default 200)

    Returns:
        dict with success and list of image paths
    """
    try:
        if not os.path.exists(pdf_path):
            return {"success": False, "error": f"PDF not found: {pdf_path}"}

        doc = fitz.open(pdf_path)
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]

        if not output_dir:
            output_dir = os.path.join(OUTPUT_DIR, f"{base_name}_pages")
        os.makedirs(output_dir, exist_ok=True)

        image_paths = []
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=matrix)
            img_path = os.path.join(output_dir, f"{base_name}_page{page_num + 1}.png")
            pix.save(img_path)
            image_paths.append(img_path)

        doc.close()
        return {"success": True, "images": image_paths,
                "count": len(image_paths),
                "message": f"Extracted {len(image_paths)} page(s) as images to {output_dir}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def extract_images_from_pdf(pdf_path: str, output_dir: str = None) -> dict:
    """
    Extract all embedded images from a PDF file.

    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save extracted images

    Returns:
        dict with success and list of image paths
    """
    try:
        if not os.path.exists(pdf_path):
            return {"success": False, "error": f"PDF not found: {pdf_path}"}

        doc = fitz.open(pdf_path)
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]

        if not output_dir:
            output_dir = os.path.join(OUTPUT_DIR, f"{base_name}_images")
        os.makedirs(output_dir, exist_ok=True)

        image_paths = []
        img_count = 0

        for page_num in range(len(doc)):
            page = doc[page_num]
            images = page.get_images(full=True)

            for img_index, img_info in enumerate(images):
                xref = img_info[0]
                base_image = doc.extract_image(xref)

                if base_image:
                    img_data = base_image["image"]
                    ext = base_image.get("ext", "png")
                    img_count += 1
                    img_path = os.path.join(output_dir, f"{base_name}_img{img_count}.{ext}")

                    with open(img_path, "wb") as f:
                        f.write(img_data)
                    image_paths.append(img_path)

        doc.close()

        if not image_paths:
            return {"success": True, "images": [], "count": 0,
                    "message": "No embedded images found in this PDF."}

        return {"success": True, "images": image_paths,
                "count": len(image_paths),
                "message": f"Extracted {len(image_paths)} image(s) to {output_dir}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def merge_pdfs(pdf_paths: list, filename: str = None) -> dict:
    """
    Merge multiple PDFs into one.

    Args:
        pdf_paths: List of PDF file paths to merge
        filename: Output filename

    Returns:
        dict with success and file path
    """
    try:
        if not filename:
            filename = f"merged_{int(time.time())}.pdf"

        _ensure_dir()
        output_path = os.path.join(OUTPUT_DIR, filename)

        merged = fitz.open()

        for pdf_path in pdf_paths:
            if os.path.exists(pdf_path):
                doc = fitz.open(pdf_path)
                merged.insert_pdf(doc)
                doc.close()

        merged.save(output_path)
        merged.close()

        return {"success": True, "path": output_path,
                "message": f"Merged {len(pdf_paths)} PDFs into {output_path}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def pdf_info(pdf_path: str) -> dict:
    """Get info about a PDF (page count, size, metadata)."""
    try:
        if not os.path.exists(pdf_path):
            return {"success": False, "error": f"PDF not found: {pdf_path}"}

        doc = fitz.open(pdf_path)
        info = {
            "success": True,
            "pages": len(doc),
            "metadata": doc.metadata,
            "file_size": os.path.getsize(pdf_path),
            "message": f"PDF has {len(doc)} page(s), {os.path.getsize(pdf_path) // 1024}KB"
        }
        doc.close()
        return info

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("PDF Tools for ARIA")
        print("  create <text> [title]     - Create PDF from text")
        print("  images2pdf <img1> [img2]  - Convert images to PDF")
        print("  pdf2images <pdf>          - Convert PDF pages to images")
        print("  extract <pdf>             - Extract images from PDF")
        print("  merge <pdf1> <pdf2>       - Merge PDFs")
        print("  info <pdf>                - Get PDF info")
    elif sys.argv[1] == "info" and len(sys.argv) > 2:
        print(pdf_info(sys.argv[2]))
