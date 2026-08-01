"""
utils.py
---------
Helper functions: QR code generation for "receive money", QR decoding
for "scan & pay", and transaction history export in multiple formats.
"""

import io
import csv
import json

import qrcode
from PIL import Image


# ---------------------------------------------------------------
# QR CODE (receive money / scan & pay)
# ---------------------------------------------------------------

QR_PREFIX = "ENZBANK-PAY:"  # simple scheme so we don't accidentally read unrelated QR codes


def generate_payment_qr(account_number: str) -> bytes:
    """Generate a QR code image (PNG bytes) encoding this account number."""
    payload = f"{QR_PREFIX}{account_number}"
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def decode_payment_qr(image_bytes: bytes):
    """
    Decode an uploaded QR code image and return the account number it
    encodes, or None if it isn't a valid ENZ Bank payment QR code.
    """
    try:
        from pyzbar.pyzbar import decode as zbar_decode
    except ImportError:
        return None, "QR scanning isn't available on this server (pyzbar not installed)."

    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        return None, "Could not read the uploaded image."

    results = zbar_decode(img)
    if not results:
        return None, "No QR code detected in the image."

    data = results[0].data.decode("utf-8", errors="ignore")
    if not data.startswith(QR_PREFIX):
        return None, "This QR code isn't a valid ENZ Bank payment code."

    account_number = data[len(QR_PREFIX):]
    return account_number, None


# ---------------------------------------------------------------
# TRANSACTION HISTORY EXPORT
# ---------------------------------------------------------------

def export_csv(transactions: list) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=["date", "date_time", "type", "amount", "balance_after", "description"]
    )
    writer.writeheader()
    for t in transactions:
        writer.writerow(t)
    return buf.getvalue().encode("utf-8")


def export_json(transactions: list) -> bytes:
    return json.dumps(transactions, indent=2).encode("utf-8")


def export_txt(transactions: list) -> bytes:
    lines = []
    for t in transactions:
        lines.append(
            f"{t['date']} {t['date_time']} | {t['type']:<20} | "
            f"₹{t['amount']:.2f} | Balance after: ₹{t['balance_after']:.2f} | {t['description']}"
        )
    return "\n".join(lines).encode("utf-8")


def export_pdf(transactions: list, account_number: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("ENZ Bank — Transaction History", styles["Title"]),
        Paragraph(f"Account Number: {account_number}", styles["Normal"]),
        Spacer(1, 12),
    ]

    data = [["Date", "Time", "Type", "Amount (₹)", "Balance After (₹)", "Description"]]
    for t in transactions:
        data.append([
            t["date"], t["date_time"], t["type"],
            f"{t['amount']:.2f}", f"{t['balance_after']:.2f}", t["description"] or "",
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f4c81")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
    ]))
    elements.append(table)
    doc.build(elements)
    return buf.getvalue()
