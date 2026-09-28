from __future__ import annotations

import importlib.util
from pathlib import Path

import streamlit as st


CORE_PATH = Path(__file__).with_name(".py")

spec = importlib.util.spec_from_file_location("bank_statement_core", CORE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load parser from {CORE_PATH}")

core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


read_bank_statement = core.read_bank_statement
upload_and_export = core.upload_and_export


st.set_page_config(page_title="Project Digital Hustle | Statement Studio", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@400;500;600;700&display=swap');
    :root { --ink:#111827; --paper:#f4f0e8; --lime:#d7f36a; --coral:#ff765c; --muted:#667085; --line:rgba(17,24,39,.13); }
    .stApp { background:var(--paper); color:var(--ink); font-family:'Space Grotesk',sans-serif; }
    .block-container { max-width:1180px; padding:2.2rem 3rem 4rem; }
    [data-testid='stHeader'] { background:transparent; }
    [data-testid='stFileUploader'] section { border:1.5px dashed var(--ink); border-radius:4px; background:rgba(255,255,255,.42); padding:1.2rem; }
    [data-testid='stFileUploader'] small { color:var(--muted); }
    .brandbar { display:flex; align-items:center; justify-content:space-between; margin-bottom:4rem; }
    .brand { display:flex; gap:.7rem; align-items:center; font-weight:700; letter-spacing:.04em; }
    .brand-mark { width:34px; height:34px; background:var(--ink); color:var(--lime); display:grid; place-items:center; font-size:18px; transform:rotate(-8deg); }
    .brand-copy { line-height:.9; font-size:.78rem; }
    .brand-copy span { display:block; font-family:'DM Mono',monospace; font-size:.52rem; letter-spacing:.15em; color:var(--coral); margin-bottom:.22rem; }
    .nav-note,.section-label { font-family:'DM Mono',monospace; color:var(--muted); font-size:.68rem; letter-spacing:.1em; text-transform:uppercase; }
    .hero { display:grid; grid-template-columns:1.2fr .8fr; gap:5rem; align-items:end; margin-bottom:4rem; }
    .eyebrow,.upload-kicker { font-family:'DM Mono',monospace; font-size:.7rem; letter-spacing:.15em; text-transform:uppercase; color:var(--coral); margin-bottom:1.2rem; }
    .hero h1 { font-size:clamp(3.5rem,8vw,7.8rem); line-height:.82; letter-spacing:-.07em; margin:0; max-width:760px; color:var(--ink); }
    .hero h1 em { color:var(--coral); font-style:normal; }
    .hero-copy { font-size:1.05rem; line-height:1.5; color:var(--muted); max-width:340px; margin:0 0 .4rem; }
    .hero-copy strong { color:var(--ink); }
    .rule { height:1px; background:var(--line); margin:0 0 2.2rem; }
    .metrics { display:grid; grid-template-columns:repeat(3,1fr); gap:1rem; margin-bottom:3rem; }
    .metric { border-top:2px solid var(--ink); padding-top:.8rem; }
    .metric strong { display:block; font-size:1.4rem; }
    .metric span { font-family:'DM Mono',monospace; font-size:.62rem; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; }
    .upload-shell { background:var(--ink); color:var(--paper); padding:2rem; border-radius:4px; position:relative; overflow:hidden; }
    .upload-shell:after { content:''; position:absolute; width:180px; height:180px; border:1px solid rgba(215,243,106,.35); border-radius:50%; right:-45px; top:-70px; }
    .upload-kicker { color:var(--lime); margin-bottom:.35rem; }
    .upload-shell h2 { font-size:2rem; letter-spacing:-.04em; margin:.35rem 0 .5rem; }
    .upload-shell p { color:#bac1ca; margin:0 0 1.2rem; }
    .upload-shell [data-testid='stFileUploader'] section { background:#202938; border-color:#8490a2; }
    .upload-shell [data-testid='stFileUploader'] label, .upload-shell [data-testid='stFileUploader'] small { color:#e7ebef; }
    .section-label { margin:2.8rem 0 1rem; }
    .footer-row { display:flex; align-items:center; justify-content:space-between; gap:1rem; }
    .coffee-button { display:inline-block; background:var(--coral); color:var(--ink) !important; padding:.75rem 1rem; border-radius:3px; font-weight:700; font-size:.78rem; text-decoration:none !important; transition:transform .2s ease, background .2s ease; }
    .coffee-button:hover { background:var(--lime); transform:translateY(-2px); }
    @media (max-width:760px) { .block-container{padding:1.4rem 1.1rem 3rem;} .brandbar{margin-bottom:2.5rem;} .hero{display:block;margin-bottom:2.7rem;} .hero h1{font-size:4.2rem;margin-bottom:1.5rem;} .metrics{gap:.6rem;} .metric strong{font-size:1.05rem;} }
    </style>
    <div class="brandbar">
        <div class="brand"><div class="brand-mark">+</div><div class="brand-copy"><span>Project</span>Digital Hustle</div></div>
        <div class="nav-note">Statement studio / 01</div>
    </div>
    <section class="hero">
        <div><div class="eyebrow">Turn paper trails into momentum</div><h1>Make your<br><em>money</em> move.</h1></div>
        <p class="hero-copy">A sharper way to turn messy bank statements into <strong>accounting-ready records</strong>. Upload once. Get clarity back.</p>
    </section>
    <div class="rule"></div>
    <div class="metrics">
        <div class="metric"><strong>01</strong><span>Drop in a PDF</span></div>
        <div class="metric"><strong>02</strong><span>Read every line</span></div>
        <div class="metric"><strong>03</strong><span>Export to Excel</span></div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="upload-shell">
        <div class="upload-kicker">Your next move</div>
        <h2>Bring the statement.</h2>
        <p>We will sort transactions into dates, descriptions, debits, credits, balances and totals.</p>
    """,
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader("Choose a PDF statement", type=["pdf"], label_visibility="visible")

st.markdown("</div>", unsafe_allow_html=True)

if uploaded_file is not None:
    try:
        records, excel_path = upload_and_export(uploaded_file, "converted_bank_statement.xlsx")

        st.success(f"Processed {len(records)} transactions successfully.")

        table_rows = [
            {
                "Date": row["Date"].strftime("%d/%m/%Y"),
                "Description": row["Description"],
                "Debit": row["Debit"],
                "Credit": row["Credit"],
                "Balance": row["Balance"],
            }
            for row in records
        ]

        st.markdown('<div class="section-label">Parsed statement</div>', unsafe_allow_html=True)
        st.dataframe(table_rows, use_container_width=True)

        with open(excel_path, "rb") as fh:
            st.download_button(
                label="Download accounting workbook",
                data=fh.read(),
                file_name="converted_bank_statement.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    except Exception as exc:
        st.error(f"Unable to process this PDF: {exc}")

st.markdown(
    """
    <div class="rule" style="margin-top:4rem"></div>
    <div class="footer-row">
        <div class="nav-note">Project Digital Hustle / Built for the business behind the numbers</div>
        <a class="coffee-button" href="https://buymeacoffee.com/saio" target="_blank" rel="noopener noreferrer">Buy me a coffee</a>
    </div>
    """,
    unsafe_allow_html=True,
)
