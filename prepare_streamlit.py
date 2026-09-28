from pathlib import Path

import streamlit


ADSENSE_TAG = (
    '<script async src="https://pagead2.googlesyndication.com/pagead/js/'
    'adsbygoogle.js?client=ca-pub-9442257999605392" '
    'crossorigin="anonymous"></script>'
)
ADSENSE_META_TAG = (
    '<meta name="google-adsense-account" '
    'content="ca-pub-9442257999605392">'
)
GOOGLE_ANALYTICS_TAG = """<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-97M6GD7RW7"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-97M6GD7RW7');
</script>"""
HEAD_TAG = "<head>"
INDEX_PATH = Path(streamlit.__file__).resolve().parent / "static" / "index.html"


html = INDEX_PATH.read_text(encoding="utf-8")
injected_tags = []
for tag in (ADSENSE_META_TAG, ADSENSE_TAG):
    if tag not in html:
        injected_tags.append(tag)
if "gtag/js?id=G-97M6GD7RW7" not in html:
    injected_tags.append(GOOGLE_ANALYTICS_TAG)

if injected_tags:
    if HEAD_TAG not in html:
        raise RuntimeError(f"Unable to find {HEAD_TAG!r} in {INDEX_PATH}")
    tags_markup = "\n    ".join(injected_tags)
    html = html.replace(HEAD_TAG, f"{HEAD_TAG}\n    {tags_markup}", 1)
    INDEX_PATH.write_text(html, encoding="utf-8")