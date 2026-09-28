<<<<<<< HEAD
import argparse
import re
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

import pdfplumber
from openpyxl import Workbook
from openpyxl.styles import Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


DATE_PATTERNS = (
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%Y/%m/%d",
    "%Y-%m-%d",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d %Y",
    "%B %d %Y",
)
DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)
MONEY_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:[+-]?\s*R\s*)?(?:\d[\d,]*\.\d{2}|\d{1,3}(?:\s\d{3})+\.\d{2}|\d+\.\d{2})(?:\s*(?:Cr|Dr))?(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def clean_line(value):
    return re.sub(r"\s+", " ", value or "").strip()


def parse_date(value, fallback_year=None):
    value = clean_line(value)
    if not value:
        return None
    for fmt in DATE_PATTERNS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    if fallback_year is not None:
        for fmt in ("%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y"):
            try:
                return datetime.strptime(f"{value} {fallback_year}", fmt).date()
            except ValueError:
                continue
    return None


def parse_money(value):
    text = str(value or "").strip()
    if not text:
        return 0.0
    text = text.replace(",", "").replace("€", "").replace("$", "").replace("£", "")
    text = text.replace(" ", "")
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"
    if text.startswith("+"):
        text = text[1:]
    if text in {"-", "--", ""}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def looks_like_money(token):
    text = (token or "").strip()
    if not text:
        return False
    if re.search(r"(?:R|[.,]\d{2}|(?:Cr|Dr))", text, re.IGNORECASE):
        return True
    return False


def detect_sign(description, amount):
    lower = (description or "").lower()
    if any(keyword in lower for keyword in ["credit", "deposit", "salary", "refund", "received", "incoming", "cr", "payment received"]):
        return abs(amount)
    if any(keyword in lower for keyword in ["debit", "withdrawal", "purchase", "rent", "transfer", "fee", "charge", "dr", "card payment", "cash"]):
        return -abs(amount)
    return amount


def extract_text_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = []
        for page in pdf.pages:
            extracted = page.extract_text() or ""
            text.append(extracted)
    return "\n".join(text)


def parse_pipe_row(line):
    if "|" not in line:
        return None
    cells = [clean_line(part) for part in line.split("|")]
    if len(cells) < 5:
        return None

    if not DATE_RE.search(cells[0]):
        return None

    date_value = parse_date(DATE_RE.search(cells[0]).group(0))
    if date_value is None:
        return None

    description = cells[1] if len(cells) > 1 else "Transaction"
    debit = parse_money(cells[2]) if len(cells) > 2 else 0.0
    credit = parse_money(cells[3]) if len(cells) > 3 else 0.0
    balance = parse_money(cells[4]) if len(cells) > 4 else 0.0

    if debit == 0.0 and credit == 0.0 and balance != 0.0:
        return None

    if debit != 0.0 and credit == 0.0 and balance != 0.0:
        return {
            "Date": date_value,
            "Description": description,
            "Debit": abs(debit),
            "Credit": 0.0,
            "Balance": balance,
        }

    if credit != 0.0 and debit == 0.0 and balance != 0.0:
        return {
            "Date": date_value,
            "Description": description,
            "Debit": 0.0,
            "Credit": abs(credit),
            "Balance": balance,
        }

    return {
        "Date": date_value,
        "Description": description,
        "Debit": abs(debit) if debit < 0 else 0.0,
        "Credit": abs(credit) if credit > 0 else 0.0,
        "Balance": balance,
    }


def parse_money_token(token):
    token_text = (token or "").strip()
    if not token_text:
        return 0.0

    clean = token_text.replace(",", "").replace(" ", "")
    if not clean:
        return 0.0

    sign = 1.0
    if clean.startswith("-"):
        sign = -1.0
        clean = clean[1:]
    elif clean.startswith("+"):
        clean = clean[1:]

    if clean.startswith("(") and clean.endswith(")"):
        sign = -1.0
        clean = clean[1:-1]

    if clean.lower().startswith("r"):
        clean = clean[1:]

    lower = clean.lower()
    if lower.endswith("dr"):
        sign = -1.0
        clean = clean[:-2]
    elif lower.endswith("cr"):
        sign = 1.0
        clean = clean[:-2]

    if not re.fullmatch(r"\d+(?:\.\d+)?", clean):
        return 0.0

    try:
        return sign * float(clean)
    except ValueError:
        return 0.0


def parse_text_row(line, fallback_year=None):
    if not DATE_RE.search(line):
        if fallback_year is None:
            return None
        month_date_match = re.search(r"\b\d{1,2}\s+[A-Za-z]{3,9}\b", line)
        if month_date_match is None:
            return None
        date_value = parse_date(month_date_match.group(0), fallback_year=fallback_year)
        if date_value is None:
            return None
        after_date = line[month_date_match.end():].strip()
    else:
        match = DATE_RE.search(line)
        date_value = parse_date(match.group(0), fallback_year=fallback_year)
        if date_value is None:
            return None
        after_date = line[match.end():].strip()

    if not after_date:
        return None

    raw_matches = list(MONEY_RE.finditer(after_date))
    matches = []
    for match in raw_matches:
        token = match.group(0)
        if not looks_like_money(token):
            continue
        value = parse_money_token(token)
        digits_only = re.sub(r"[^\d]", "", token)
        if not re.search(r"(?:R|(?:Cr|Dr))", token, re.IGNORECASE) and not re.search(r"\d[.,]\d", token):
            if len(digits_only) <= 4:
                continue
        if value == 0.0 and not re.search(r"(?:R|[.,]\d{2}|(?:Cr|Dr))", token, re.IGNORECASE):
            continue
        matches.append((match, value))
    if len(matches) < 2:
        return None

    short_date_row = bool(re.match(r"^\d{1,2}\s+[A-Za-z]{3,9}\b", line))
    if short_date_row:
        amount_match, amount = matches[0]
        balance_match, balance = matches[1]
    else:
        amount_match, amount = matches[-2]
        balance_match, balance = matches[-1]
    amount_token = amount_match.group(0)
    balance_token = balance_match.group(0)

    if amount == 0 and ("0.00" in amount_token or "0.00" in balance_token):
        return None

    description = after_date[: amount_match.start()].strip(" -:;|")
    if not description:
        description = after_date[: balance_match.start()].strip(" -:;|")
    if not description:
        description = "Transaction"

    lower_description = description.lower()
    if any(keyword in lower_description for keyword in ["proof", "pmt", "paymt", "email", "sms", "balance brought forward"]):
        if abs(amount) <= 0.01:
            return None

    amount_is_credit = bool(re.search(r"cr\s*$", amount_token, re.IGNORECASE))
    description_is_credit = bool(re.search(
        r"\b(?:credit|deposit|salary|refund|received|incoming)\b",
        lower_description,
        re.IGNORECASE,
    ))
    if amount < 0:
        debit = abs(amount)
        credit = 0.0
    elif amount_is_credit or description_is_credit:
        debit = 0.0
        credit = abs(amount)
    elif short_date_row:
        debit = abs(amount)
        credit = 0.0
    else:
        debit = 0.0
        credit = abs(amount)

    return {
        "Date": date_value,
        "Description": description,
        "Debit": debit,
        "Credit": credit,
        "Balance": balance,
    }


def parse_bank_statement(pdf_path):
    text = extract_text_from_pdf(pdf_path)
    records = []
    statement_year = None

    for raw_line in text.splitlines():
        line = clean_line(raw_line)
        if not line:
            continue
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", line)
        if year_match and ("Statement Period" in line or "Statement Date" in line or "Statement" in line):
            statement_year = int(year_match.group(1))

    for raw_line in text.splitlines():
        line = clean_line(raw_line)
        if not line:
            continue
        record = parse_pipe_row(line)
        if record is None:
            record = parse_text_row(line, fallback_year=statement_year)
        if record is None:
            continue
        if record["Description"].lower() in {"date", "description", "debit", "credit", "balance", "transaction"}:
            continue
        records.append(record)

    if not records:
        raise ValueError("No valid bank transactions were found in the PDF.")

    records.sort(key=lambda item: item["Date"])

    running_balance = 0.0
    normalized = []
    for record in records:
        balance = record.get("Balance")
        if balance not in (None, 0.0, ""):
            running_balance = float(balance)
        else:
            running_balance += float(record["Credit"]) - float(record["Debit"])
            record["Balance"] = running_balance
        normalized.append(
            {
                "Date": record["Date"],
                "Description": record["Description"],
                "Debit": round(float(record["Debit"]), 2),
                "Credit": round(float(record["Credit"]), 2),
                "Balance": round(float(record["Balance"]), 2),
            }
        )

    return normalized


def generate_demo_bank_statement(pdf_path):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    output_path = Path(pdf_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(output_path), pagesize=letter)
    c.setTitle("Demo Bank Statement")
    c.setFont("Helvetica-Bold", 18)
    c.drawString(60, 760, "Bank Statement")
    c.setFont("Helvetica", 10)

    rows = [
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["01/09/2026", "Salary Deposit", "", "2500.00", "2500.00"],
        ["02/09/2026", "Rent", "1200.00", "", "1300.00"],
        ["03/09/2026", "Supermarket Purchase", "85.50", "", "1214.50"],
        ["05/09/2026", "Client Payment", "", "500.00", "1714.50"],
    ]

    y = 720
    for row in rows:
        x = 60
        for cell in row:
            c.drawString(x, y, str(cell))
            x += 120
        y -= 20

    c.save()
    return str(output_path)


def export_to_excel(records, output_excel_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Bank Statement"

    headers = ["Date", "Description", "Debit", "Credit", "Balance"]
    sheet.append(headers)
    for item in records:
        sheet.append([
            item["Date"].strftime("%d/%m/%Y"),
            item["Description"],
            item["Debit"],
            item["Credit"],
            item["Balance"],
        ])

    header_fill = PatternFill("solid", fgColor="D9EAF7")
    header_font = Font(bold=True)
    thin = Side(style="thin", color="D9D9D9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border

    for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row, min_col=1, max_col=5):
        for cell in row:
            cell.border = border

    for row_idx in range(2, sheet.max_row + 1):
        for column_letter in ["C", "D", "E"]:
            cell = sheet[f"{column_letter}{row_idx}"]
            cell.number_format = '[$$-en-US]#,##0.00'

    for column_cells in sheet.columns:
        max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
        sheet.column_dimensions[get_column_letter(column_cells[0].column)].width = max_len + 2

    sheet.freeze_panes = "A2"
    sheet["F2"] = "Total Debits"
    sheet["G2"] = f"=SUM(C2:C{sheet.max_row})"
    sheet["F3"] = "Total Credits"
    sheet["G3"] = f"=SUM(D2:D{sheet.max_row})"
    sheet["F4"] = "Net Movement"
    sheet["G4"] = f"=SUM(D2:D{sheet.max_row})-SUM(C2:C{sheet.max_row})"

    for row_idx in [2, 3, 4]:
        sheet[f"F{row_idx}"].font = Font(bold=True)
        sheet[f"G{row_idx}"].number_format = '[$$-en-US]#,##0.00'

    sheet["F6"] = "Opening Balance"
    sheet["G6"] = "=SUM(E2)"
    sheet["F7"] = "Closing Balance"
    sheet["G7"] = f"=E{sheet.max_row}"
    sheet["F8"] = "Difference"
    sheet["G8"] = f"=G7-G6"

    for summary_cell in ["G6", "G7", "G8"]:
        sheet[summary_cell].number_format = '[$$-en-US]#,##0.00'

    output_path = Path(output_excel_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    return output_path


def read_bank_statement(pdf_path, output_excel_path):
    records = parse_bank_statement(pdf_path)
    output_path = export_to_excel(records, output_excel_path)
    return records, output_path


def upload_and_export(uploaded_pdf, output_name="bank_statement.xlsx"):
    with NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
        temp_pdf.write(uploaded_pdf.read())
        temp_pdf_path = temp_pdf.name

    try:
        records, output_path = read_bank_statement(temp_pdf_path, output_name)
        return records, str(output_path)
    finally:
        try:
            Path(temp_pdf_path).unlink(missing_ok=True)
        except Exception:
            pass


def run_streamlit_app():
    try:
        import streamlit as st
    except ImportError:
        raise RuntimeError("Install streamlit to use the uploader app: pip install streamlit")

    st.set_page_config(page_title="Bank Statement to Excel", layout="wide")
    st.title("Bank Statement PDF to Excel")

    uploaded_file = st.file_uploader("Upload a PDF bank statement", type=["pdf"])

    if uploaded_file is not None:
        records, excel_path = upload_and_export(uploaded_file, "converted_bank_statement.xlsx")
        st.success(f"Successfully processed {len(records)} transactions.")

        data = [{
            "Date": row["Date"].strftime("%d/%m/%Y"),
            "Description": row["Description"],
            "Debit": row["Debit"],
            "Credit": row["Credit"],
            "Balance": row["Balance"],
        } for row in records]
        st.dataframe(data, use_container_width=True)

        with open(excel_path, "rb") as fh:
            st.download_button(
                label="Download Excel",
                data=fh.read(),
                file_name="converted_bank_statement.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read a PDF bank statement and export it to an accounting Excel file.")
    parser.add_argument("pdf_path", nargs="?", default="", help="Path to the bank statement PDF to process.")
    parser.add_argument("output_excel_path", nargs="?", default="bank_statement.xlsx", help="Output Excel path.")
    parser.add_argument("--create-demo", action="store_true", help="Generate a sample PDF before parsing.")
    parser.add_argument("--streamlit", action="store_true", help="Launch the upload-based web app.")
    args = parser.parse_args()

    if args.streamlit:
        run_streamlit_app()
    elif args.create_demo:
        pdf_path = args.pdf_path or "demo_bank_statement.pdf"
        generate_demo_bank_statement(pdf_path)
        read_bank_statement(pdf_path, args.output_excel_path)
    else:
        if not args.pdf_path:
            raise ValueError("Provide a PDF path or use --create-demo.")
        read_bank_statement(args.pdf_path, args.output_excel_path)
=======
import argparse
import re
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

import pdfplumber
from openpyxl import Workbook
from openpyxl.styles import Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


DATE_PATTERNS = (
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%Y/%m/%d",
    "%Y-%m-%d",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d %Y",
    "%B %d %Y",
)
DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)
MONEY_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:[+-]?\s*R\s*)?(?:\d[\d,]*\.\d{2}|\d{1,3}(?:\s\d{3})+\.\d{2}|\d+\.\d{2})(?:\s*(?:Cr|Dr))?(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def clean_line(value):
    return re.sub(r"\s+", " ", value or "").strip()


def parse_date(value, fallback_year=None):
    value = clean_line(value)
    if not value:
        return None
    for fmt in DATE_PATTERNS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    if fallback_year is not None:
        for fmt in ("%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y"):
            try:
                return datetime.strptime(f"{value} {fallback_year}", fmt).date()
            except ValueError:
                continue
    return None


def parse_money(value):
    text = str(value or "").strip()
    if not text:
        return 0.0
    text = text.replace(",", "").replace("€", "").replace("$", "").replace("£", "")
    text = text.replace(" ", "")
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"
    if text.startswith("+"):
        text = text[1:]
    if text in {"-", "--", ""}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def looks_like_money(token):
    text = (token or "").strip()
    if not text:
        return False
    if re.search(r"(?:R|[.,]\d{2}|(?:Cr|Dr))", text, re.IGNORECASE):
        return True
    return False


def detect_sign(description, amount):
    lower = (description or "").lower()
    if any(keyword in lower for keyword in ["credit", "deposit", "salary", "refund", "received", "incoming", "cr", "payment received"]):
        return abs(amount)
    if any(keyword in lower for keyword in ["debit", "withdrawal", "purchase", "rent", "transfer", "fee", "charge", "dr", "card payment", "cash"]):
        return -abs(amount)
    return amount


def extract_text_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = []
        for page in pdf.pages:
            extracted = page.extract_text() or ""
            text.append(extracted)
    return "\n".join(text)


def parse_pipe_row(line):
    if "|" not in line:
        return None
    cells = [clean_line(part) for part in line.split("|")]
    if len(cells) < 5:
        return None

    if not DATE_RE.search(cells[0]):
        return None

    date_value = parse_date(DATE_RE.search(cells[0]).group(0))
    if date_value is None:
        return None

    description = cells[1] if len(cells) > 1 else "Transaction"
    debit = parse_money(cells[2]) if len(cells) > 2 else 0.0
    credit = parse_money(cells[3]) if len(cells) > 3 else 0.0
    balance = parse_money(cells[4]) if len(cells) > 4 else 0.0

    if debit == 0.0 and credit == 0.0 and balance != 0.0:
        return None

    if debit != 0.0 and credit == 0.0 and balance != 0.0:
        return {
            "Date": date_value,
            "Description": description,
            "Debit": abs(debit),
            "Credit": 0.0,
            "Balance": balance,
        }

    if credit != 0.0 and debit == 0.0 and balance != 0.0:
        return {
            "Date": date_value,
            "Description": description,
            "Debit": 0.0,
            "Credit": abs(credit),
            "Balance": balance,
        }

    return {
        "Date": date_value,
        "Description": description,
        "Debit": abs(debit) if debit < 0 else 0.0,
        "Credit": abs(credit) if credit > 0 else 0.0,
        "Balance": balance,
    }


def parse_money_token(token):
    token_text = (token or "").strip()
    if not token_text:
        return 0.0

    clean = token_text.replace(",", "").replace(" ", "")
    if not clean:
        return 0.0

    sign = 1.0
    if clean.startswith("-"):
        sign = -1.0
        clean = clean[1:]
    elif clean.startswith("+"):
        clean = clean[1:]

    if clean.startswith("(") and clean.endswith(")"):
        sign = -1.0
        clean = clean[1:-1]

    if clean.lower().startswith("r"):
        clean = clean[1:]

    lower = clean.lower()
    if lower.endswith("dr"):
        sign = -1.0
        clean = clean[:-2]
    elif lower.endswith("cr"):
        sign = 1.0
        clean = clean[:-2]

    if not re.fullmatch(r"\d+(?:\.\d+)?", clean):
        return 0.0

    try:
        return sign * float(clean)
    except ValueError:
        return 0.0


def parse_text_row(line, fallback_year=None):
    if not DATE_RE.search(line):
        if fallback_year is None:
            return None
        month_date_match = re.search(r"\b\d{1,2}\s+[A-Za-z]{3,9}\b", line)
        if month_date_match is None:
            return None
        date_value = parse_date(month_date_match.group(0), fallback_year=fallback_year)
        if date_value is None:
            return None
        after_date = line[month_date_match.end():].strip()
    else:
        match = DATE_RE.search(line)
        date_value = parse_date(match.group(0), fallback_year=fallback_year)
        if date_value is None:
            return None
        after_date = line[match.end():].strip()

    if not after_date:
        return None

    raw_matches = list(MONEY_RE.finditer(after_date))
    matches = []
    for match in raw_matches:
        token = match.group(0)
        if not looks_like_money(token):
            continue
        value = parse_money_token(token)
        digits_only = re.sub(r"[^\d]", "", token)
        if not re.search(r"(?:R|(?:Cr|Dr))", token, re.IGNORECASE) and not re.search(r"\d[.,]\d", token):
            if len(digits_only) <= 4:
                continue
        if value == 0.0 and not re.search(r"(?:R|[.,]\d{2}|(?:Cr|Dr))", token, re.IGNORECASE):
            continue
        matches.append((match, value))
    if len(matches) < 2:
        return None

    short_date_row = bool(re.match(r"^\d{1,2}\s+[A-Za-z]{3,9}\b", line))
    if short_date_row:
        amount_match, amount = matches[0]
        balance_match, balance = matches[1]
    else:
        amount_match, amount = matches[-2]
        balance_match, balance = matches[-1]
    amount_token = amount_match.group(0)
    balance_token = balance_match.group(0)

    if amount == 0 and ("0.00" in amount_token or "0.00" in balance_token):
        return None

    description = after_date[: amount_match.start()].strip(" -:;|")
    if not description:
        description = after_date[: balance_match.start()].strip(" -:;|")
    if not description:
        description = "Transaction"

    lower_description = description.lower()
    if any(keyword in lower_description for keyword in ["proof", "pmt", "paymt", "email", "sms", "balance brought forward"]):
        if abs(amount) <= 0.01:
            return None

    amount_is_credit = bool(re.search(r"cr\s*$", amount_token, re.IGNORECASE))
    description_is_credit = bool(re.search(
        r"\b(?:credit|deposit|salary|refund|received|incoming)\b",
        lower_description,
        re.IGNORECASE,
    ))
    if amount < 0:
        debit = abs(amount)
        credit = 0.0
    elif amount_is_credit or description_is_credit:
        debit = 0.0
        credit = abs(amount)
    elif short_date_row:
        debit = abs(amount)
        credit = 0.0
    else:
        debit = 0.0
        credit = abs(amount)

    return {
        "Date": date_value,
        "Description": description,
        "Debit": debit,
        "Credit": credit,
        "Balance": balance,
    }


def parse_bank_statement(pdf_path):
    text = extract_text_from_pdf(pdf_path)
    records = []
    statement_year = None

    for raw_line in text.splitlines():
        line = clean_line(raw_line)
        if not line:
            continue
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", line)
        if year_match and ("Statement Period" in line or "Statement Date" in line or "Statement" in line):
            statement_year = int(year_match.group(1))

    for raw_line in text.splitlines():
        line = clean_line(raw_line)
        if not line:
            continue
        record = parse_pipe_row(line)
        if record is None:
            record = parse_text_row(line, fallback_year=statement_year)
        if record is None:
            continue
        if record["Description"].lower() in {"date", "description", "debit", "credit", "balance", "transaction"}:
            continue
        records.append(record)

    if not records:
        raise ValueError("No valid bank transactions were found in the PDF.")

    records.sort(key=lambda item: item["Date"])

    running_balance = 0.0
    normalized = []
    for record in records:
        balance = record.get("Balance")
        if balance not in (None, 0.0, ""):
            running_balance = float(balance)
        else:
            running_balance += float(record["Credit"]) - float(record["Debit"])
            record["Balance"] = running_balance
        normalized.append(
            {
                "Date": record["Date"],
                "Description": record["Description"],
                "Debit": round(float(record["Debit"]), 2),
                "Credit": round(float(record["Credit"]), 2),
                "Balance": round(float(record["Balance"]), 2),
            }
        )

    return normalized


def generate_demo_bank_statement(pdf_path):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    output_path = Path(pdf_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(output_path), pagesize=letter)
    c.setTitle("Demo Bank Statement")
    c.setFont("Helvetica-Bold", 18)
    c.drawString(60, 760, "Bank Statement")
    c.setFont("Helvetica", 10)

    rows = [
        ["Date", "Description", "Debit", "Credit", "Balance"],
        ["01/09/2026", "Salary Deposit", "", "2500.00", "2500.00"],
        ["02/09/2026", "Rent", "1200.00", "", "1300.00"],
        ["03/09/2026", "Supermarket Purchase", "85.50", "", "1214.50"],
        ["05/09/2026", "Client Payment", "", "500.00", "1714.50"],
    ]

    y = 720
    for row in rows:
        x = 60
        for cell in row:
            c.drawString(x, y, str(cell))
            x += 120
        y -= 20

    c.save()
    return str(output_path)


def export_to_excel(records, output_excel_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Bank Statement"

    headers = ["Date", "Description", "Debit", "Credit", "Balance"]
    sheet.append(headers)
    for item in records:
        sheet.append([
            item["Date"].strftime("%d/%m/%Y"),
            item["Description"],
            item["Debit"],
            item["Credit"],
            item["Balance"],
        ])

    header_fill = PatternFill("solid", fgColor="D9EAF7")
    header_font = Font(bold=True)
    thin = Side(style="thin", color="D9D9D9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border

    for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row, min_col=1, max_col=5):
        for cell in row:
            cell.border = border

    for row_idx in range(2, sheet.max_row + 1):
        for column_letter in ["C", "D", "E"]:
            cell = sheet[f"{column_letter}{row_idx}"]
            cell.number_format = '[$$-en-US]#,##0.00'

    for column_cells in sheet.columns:
        max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
        sheet.column_dimensions[get_column_letter(column_cells[0].column)].width = max_len + 2

    sheet.freeze_panes = "A2"
    sheet["F2"] = "Total Debits"
    sheet["G2"] = f"=SUM(C2:C{sheet.max_row})"
    sheet["F3"] = "Total Credits"
    sheet["G3"] = f"=SUM(D2:D{sheet.max_row})"
    sheet["F4"] = "Net Movement"
    sheet["G4"] = f"=SUM(D2:D{sheet.max_row})-SUM(C2:C{sheet.max_row})"

    for row_idx in [2, 3, 4]:
        sheet[f"F{row_idx}"].font = Font(bold=True)
        sheet[f"G{row_idx}"].number_format = '[$$-en-US]#,##0.00'

    sheet["F6"] = "Opening Balance"
    sheet["G6"] = "=SUM(E2)"
    sheet["F7"] = "Closing Balance"
    sheet["G7"] = f"=E{sheet.max_row}"
    sheet["F8"] = "Difference"
    sheet["G8"] = f"=G7-G6"

    for summary_cell in ["G6", "G7", "G8"]:
        sheet[summary_cell].number_format = '[$$-en-US]#,##0.00'

    output_path = Path(output_excel_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    return output_path


def read_bank_statement(pdf_path, output_excel_path):
    records = parse_bank_statement(pdf_path)
    output_path = export_to_excel(records, output_excel_path)
    return records, output_path


def upload_and_export(uploaded_pdf, output_name="bank_statement.xlsx"):
    with NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
        temp_pdf.write(uploaded_pdf.read())
        temp_pdf_path = temp_pdf.name

    try:
        records, output_path = read_bank_statement(temp_pdf_path, output_name)
        return records, str(output_path)
    finally:
        try:
            Path(temp_pdf_path).unlink(missing_ok=True)
        except Exception:
            pass


def run_streamlit_app():
    try:
        import streamlit as st
    except ImportError:
        raise RuntimeError("Install streamlit to use the uploader app: pip install streamlit")

    st.set_page_config(page_title="Bank Statement to Excel", layout="wide")
    st.title("Bank Statement PDF to Excel")

    uploaded_file = st.file_uploader("Upload a PDF bank statement", type=["pdf"])

    if uploaded_file is not None:
        records, excel_path = upload_and_export(uploaded_file, "converted_bank_statement.xlsx")
        st.success(f"Successfully processed {len(records)} transactions.")

        data = [{
            "Date": row["Date"].strftime("%d/%m/%Y"),
            "Description": row["Description"],
            "Debit": row["Debit"],
            "Credit": row["Credit"],
            "Balance": row["Balance"],
        } for row in records]
        st.dataframe(data, use_container_width=True)

        with open(excel_path, "rb") as fh:
            st.download_button(
                label="Download Excel",
                data=fh.read(),
                file_name="converted_bank_statement.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read a PDF bank statement and export it to an accounting Excel file.")
    parser.add_argument("pdf_path", nargs="?", default="", help="Path to the bank statement PDF to process.")
    parser.add_argument("output_excel_path", nargs="?", default="bank_statement.xlsx", help="Output Excel path.")
    parser.add_argument("--create-demo", action="store_true", help="Generate a sample PDF before parsing.")
    parser.add_argument("--streamlit", action="store_true", help="Launch the upload-based web app.")
    args = parser.parse_args()

    if args.streamlit:
        run_streamlit_app()
    elif args.create_demo:
        pdf_path = args.pdf_path or "demo_bank_statement.pdf"
        generate_demo_bank_statement(pdf_path)
        read_bank_statement(pdf_path, args.output_excel_path)
    else:
        if not args.pdf_path:
            raise ValueError("Provide a PDF path or use --create-demo.")
        read_bank_statement(args.pdf_path, args.output_excel_path)
>>>>>>> c40f766 (Deploy Project Digital Hustle app)
