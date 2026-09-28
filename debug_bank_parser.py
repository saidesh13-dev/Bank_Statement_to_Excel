import importlib.util
from pathlib import Path

p = Path('.py')
spec = importlib.util.spec_from_file_location('core', p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

pdfs = [
    Path(r'C:\Users\saide\Downloads\66aaf8d50a2c9b4f97b3713bd57dca5d.pdf'),
    Path(r'C:\Users\saide\Downloads\SOZA WASTE MANAGEMENT (PTY) LTD_2026-07-01_2026-07-31_stamped (1).pdf'),
]

for pdf in pdfs:
    print('FILE', pdf)
    text = mod.extract_text_from_pdf(str(pdf))
    lines = [line for line in text.splitlines() if line.strip()]
    for line in lines[:120]:
        if any(key in line.lower() for key in ['2026', 'date', 'balance', 'proof', 'payment', 'amount', 'credit', 'debit', 'transaction', 'pmt', 'dr', 'cr']):
            print(line)
    print('--- text end ---')
    try:
        recs = mod.parse_bank_statement(str(pdf))
        print('COUNT', len(recs))
        for row in recs[:20]:
            print(row)
    except Exception as exc:
        print('ERROR', type(exc).__name__, exc)
    print('=== FILE END ===\n')
