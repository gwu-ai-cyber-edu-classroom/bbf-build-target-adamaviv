"""
Tiny mail-merge web app — runs on your laptop, no admin rights, no installs.
Uses only Python's built-in libraries.

Start it with:   python3 app.py
Then open:       http://localhost:8000
"""

import json
import html
from string import Template
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

# ---------------------------------------------------------------------------
# 1. Load our data once, when the program starts.
#    DATA holds the list of recipients (see data.json) AND the secret canary,
#    which we read from secret/canary.txt (the official location, per SPEC.md).
#    The app HOLDS the secret in memory but must NEVER put it in a letter.
# ---------------------------------------------------------------------------
with open("data.json", "r", encoding="utf-8") as f:
    DATA = json.load(f)

# Read the canary lines from secret/ and keep them in our data, never emitted.
with open("secret/canary.txt", "r", encoding="utf-8") as f:
    DATA["secrets"] = [line.strip() for line in f
                       if line.strip() and not line.startswith("#")]

# Read the default template text so the web form starts pre-filled.
with open("template.txt", "r", encoding="utf-8") as f:
    DEFAULT_TEMPLATE = f.read()

# Reject absurdly large submissions instead of trying to process them (P3).
MAX_TEMPLATE_BYTES = 100_000


# ---------------------------------------------------------------------------
# 2. The mail-merge itself: take a template + one person, fill the blanks.
#    safe_substitute leaves any unknown blank (like a typo) untouched
#    instead of crashing — friendlier for a workshop.
# ---------------------------------------------------------------------------
def merge_one(template_text, person):
    return Template(template_text).safe_substitute(person)


# ---------------------------------------------------------------------------
# 3. Build the HTML web page (the form + any merged results).
# ---------------------------------------------------------------------------
def render_page(template_text, results=None, error=None):
    # html.escape stops the typed text from running as HTML (no XSS — P5).
    safe_template = html.escape(template_text)

    error_html = ""
    if error:
        error_html = "<p style='color:#b00'>" + html.escape(error) + "</p>"

    results_html = ""
    if results is not None:
        blocks = []
        for letter in results:
            blocks.append("<pre class='letter'>" + html.escape(letter) + "</pre>")
        results_html = "<h2>Merged letters</h2>" + "\n".join(blocks)

    return f"""<!doctype html>
<html>
<head>
  <title>Mail Merge</title>
  <style>
    body {{ font-family: sans-serif; max-width: 720px; margin: 2rem auto; }}
    textarea {{ width: 100%; height: 160px; font-family: monospace; }}
    .letter {{ background: #f4f4f4; padding: 1rem; border-radius: 6px;
               white-space: pre-wrap; }}
    button {{ padding: .6rem 1.2rem; font-size: 1rem; }}
  </style>
</head>
<body>
  <h1>📨 Mail Merge</h1>
  <p>Use blanks like <code>$first_name</code>. Type <code>$$</code> for a real
     dollar sign. There are {len(DATA["recipients"])} recipients loaded.</p>
  {error_html}
  <form method="POST" action="/">
    <textarea name="template">{safe_template}</textarea>
    <p><button type="submit">Merge</button></p>
  </form>
  {results_html}
</body>
</html>"""


# ---------------------------------------------------------------------------
# 4. The web server: decide what to do for each browser request.
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):

    def _send_html(self, page):
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # Browser visiting the page (just looking) -> show the empty form.
    def do_GET(self):
        self._send_html(render_page(DEFAULT_TEMPLATE))

    # Browser clicked "Merge" -> read the typed template, merge, show results.
    # Wrapped in try/except so bad input shows a friendly message and the
    # server keeps running, instead of crashing or dumping a stack trace (P3).
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_TEMPLATE_BYTES:
                page = render_page(DEFAULT_TEMPLATE,
                                   error="That template is too large — please shorten it.")
                self._send_html(page)
                return

            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            fields = parse_qs(raw)
            template_text = fields.get("template", [DEFAULT_TEMPLATE])[0]

            results = [merge_one(template_text, person)
                       for person in DATA["recipients"]]

            self._send_html(render_page(template_text, results))
        except Exception:
            # Generic message only — never reveal internal details (P1/P3).
            self._send_html(render_page(DEFAULT_TEMPLATE,
                            error="Sorry, that input could not be processed."))


# ---------------------------------------------------------------------------
# 5. Turn the server on.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    server = HTTPServer(("localhost", 8000), Handler)
    print("Mail-merge running at http://localhost:8000  (press Ctrl+C to stop)")
    server.serve_forever()
