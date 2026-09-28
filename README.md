# Project Digital Hustle

Project Digital Hustle Statement Studio converts PDF bank statements into accounting-ready Excel workbooks.

## Run locally

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Render

This repository includes `render.yaml`. Create a new Render Blueprint from the GitHub repository. Render will install the requirements and run:

```text
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```
