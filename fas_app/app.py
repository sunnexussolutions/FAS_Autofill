#!/usr/bin/env python3
"""
Sandip University — FAS Form Auto-Filler
=========================================
Run:   python app.py
Open:  http://localhost:8765
"""
import sys, io, datetime, json, threading, webbrowser, os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── auto-install ───────────────────────────────────────────────────────────────
def _pip(pkg):
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", pkg])

for _p in ["pypdf", "reportlab", "pandas", "openpyxl"]:
    try:
        __import__(_p)
    except ImportError:
        print(f"  Installing {_p}..."); _pip(_p)

import pandas as pd
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas

# ── paths ──────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")
COORD_FILE = os.path.join(DATA_DIR, "coordinator.json")
os.makedirs(DATA_DIR, exist_ok=True)

# ── coordinator helpers ────────────────────────────────────────────────────────
def load_coordinator():
    if os.path.exists(COORD_FILE):
        try:
            return json.load(open(COORD_FILE, encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_coordinator(data):
    json.dump(data, open(COORD_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

def clear_coordinator():
    if os.path.exists(COORD_FILE):
        os.remove(COORD_FILE)

# ── in-memory state ────────────────────────────────────────────────────────────
STATE = {"students": {}, "pdf_bytes": None}

# ══════════════════════════════════════════════════════════════════════════════
#  PDF FILL ENGINE
#  Coordinates extracted from FAS_form.pdf using pdfplumber.
#  Page height = 792 pt.  pdfplumber y = from top; reportlab y = from bottom.
#  cy(y0,y1) = 792 - (y0+y1)/2  →  vertical centre of a table row.
# ══════════════════════════════════════════════════════════════════════════════
def fill_fas_form(student, pdf_bytes, coordinator=None):
    PH = 792.0

    def clean(v):
        t = str(v).strip()
        return "" if t in ("nan", "None", "NaT", "NaN") else t

    s = {k: clean(v) for k, v in student.items()}
    def g(k): return s.get(k, "")

    def fmt_date(v):
        if not v: return ""
        try:   return pd.to_datetime(v).strftime("%d/%m/%Y")
        except: return v

    dob   = fmt_date(g("dob"))
    adm   = g("Yearofadmission").split("-")[0].split("/")[0]
    today = datetime.date.today().strftime("%d/%m/%Y")

    def cy(y0, y1):
        return PH - (y0 + y1) / 2.0

    def make_layer(pts):
        buf = io.BytesIO()
        c   = rl_canvas.Canvas(buf, pagesize=(612, PH))
        c.setFillColorRGB(0, 0, 0)
        for x, y, text, fs in pts:
            if text:
                c.setFont("Helvetica", fs)
                c.drawString(float(x), float(y), str(text)[:160])
        c.save(); buf.seek(0)
        return PdfReader(buf)

    # ── PAGE 0 · Cover ────────────────────────────────────────────────────────
    # Each label line measured (y0, y1):
    #   Student Name 510.35–532.43  School Name 535.82–557.90
    #   Department   561.02–583.10  Programme   586.22–608.30
    #   PRN          611.68–633.76  Year Adm.   636.88–658.96
    # Data placed after the dots at x = 295
    p1 = [
        (295, cy(510.35, 532.43), g("student_name"),   9.5),
        (295, cy(535.82, 557.90), g("SchoolName"),      9.5),
        (295, cy(561.02, 583.10), g("DepartmentName"),  9.5),
        (295, cy(586.22, 608.30), g("Programme"),       9.5),
        (295, cy(611.68, 633.76), g("prn"),             9.5),
        (295, cy(636.88, 658.96), adm,                  9.5),
    ]

    # ── PAGE 1 · Mentor Information (both tables on same page) ────────────────
    # Two 7-row tables.  Data column starts at x = 273.70 → place at 277.
    # Table 0 (top):   row y0 values start at 185.33
    # Table 1 (bottom): row y0 values start at 509.18
    coord = coordinator or {}
    def gc(k): return str(coord.get(k, ""))
    DX = 277

    # (y0, y1, coordinator_key)  — in order: Name/School/Dept/Contact/Email/NoMentee/Class
    TABLE0 = [
        (185.33, 214.63, "mentorName"),
        (214.63, 233.59, "mentorSchool"),
        (233.59, 252.55, "mentorDept"),
        (252.55, 272.23, "mentorContact"),
        (272.23, 291.22, "mentorEmail"),
        (291.22, 310.18, "mentorNoMentee"),
        (310.18, 329.14, "mentorClass"),
    ]
    TABLE1 = [
        (509.18, 538.22, "mentorName"),
        (538.22, 557.21, "mentorSchool"),
        (557.21, 575.93, "mentorDept"),
        (575.93, 595.85, "mentorContact"),
        (595.85, 614.81, "mentorEmail"),
        (614.81, 633.55, "mentorNoMentee"),
        (633.55, 652.75, "mentorClass"),
    ]
    p2 = [(DX, cy(y0, y1), gc(k), 9) for y0, y1, k in TABLE0 + TABLE1]

    # ── PAGE 3 · Student Details (Page 1 of 3) ───────────────────────────────
    # Table 0: 9 rows, right column x = 228.82 → data at 232
    # Address boxes:  Permanent left (x=72.74–306.60), Present right (x=306.60–540.43)
    #                 box y = 325.06–449.88; text at PH-340, pincode at PH-433
    # Parents Table 2 (merged row 501.98–571.61):
    #   Mother y=517.77–529.77 at x=211 (mob1) x=446 (mob2)
    #   Father y=545.40–557.40 at x=196 (mob1) x=429 (mob2)
    # Guardian dot lines y=615.24–627.24; mobile y=672.62–684.62 x=262
    DX2 = 232
    p4 = [
        (DX2, cy(169.25, 184.13), g("SchoolName"),         9),
        (DX2, cy(184.13, 198.53), g("DepartmentName"),     9),
        (DX2, cy(198.53, 212.71), g("HostelerDayScholar"), 9),
        (DX2, cy(212.71, 227.11), g("Programme"),          9),
        (DX2, cy(227.11, 241.27), adm,                     9),
        (DX2, cy(241.27, 255.67), g("student_name"),       9),
        (DX2, cy(255.67, 270.07), g("prn"),                9),
        (DX2, cy(270.07, 284.23), dob,                     9),
        (DX2, cy(284.23, 298.42), g("mobile_number"),      9),
        # Postal address (free line below table)
        (162, cy(300.53, 312.53), g("PostalAddress"),    8.5),
        # Address boxes
        (78,  PH - 340,  g("PermanentAddress"),            8),
        (312, PH - 340,  g("PresentAddress"),              8),
        (78,  PH - 433,  g("PermanentPincode"),            8),
        (312, PH - 433,  g("PresentPincode"),              8),
        # Parent mobiles
        (211, cy(517.77, 529.77), g("MotherMobileNumber1"), 9),
        (446, cy(517.77, 529.77), g("MotherMobileNumber2"), 9),
        (196, cy(545.40, 557.40), g("FatherMobileNumber1"), 9),
        (429, cy(545.40, 557.40), g("FatherMobileNumber2"), 9),
        # Guardian
        (73,  cy(615.24, 627.24),
         ", ".join(filter(None, [g("GuardianName"), g("GuardianAddress")])), 8.5),
        (262, cy(672.62, 684.62), g("GuardianMobile"),      9),
    ]

    # ── PAGE 4 · Educational + Family + Hobbies (Page 2 of 3) ────────────────
    # Educational Table 0: Board x=219 Year x=369 Grade x=439
    #   SSC    151.25–165.41   HSC    165.41–179.57   Diploma 179.57–207.91
    # Family Table 1: Name x=114 Age x=350 Occ x=413
    #   Father 288.07–301.30  Mother 301.30–314.50
    #   Sib1   314.50–327.46  Sib2   327.46–340.66  Sib3 340.66–353.62
    # Hobbies dot line y=380.98–393.46 at x=73
    # Co-curr Table 2: Activity x=153 Achievement x=350  row 456.12–481.82
    BD, YR, GR = 219, 369, 439
    NX, AX, OX = 114, 350, 413
    p5 = [
        (BD, cy(151.25, 165.41), g("SSCBoard"),          9),
        (YR, cy(151.25, 165.41), g("SSCYear"),           9),
        (GR, cy(151.25, 165.41), g("SSCPercentage"),     9),
        (BD, cy(165.41, 179.57), g("HSCBoard"),          9),
        (YR, cy(165.41, 179.57), g("HSCYear"),           9),
        (GR, cy(165.41, 179.57), g("HSCPercentage"),     9),
        (BD, cy(179.57, 207.91), g("DiplomaCollege"),    9),
        (YR, cy(179.57, 207.91), g("DiplomaYear"),       9),
        (GR, cy(179.57, 207.91), g("DiplomaPercentage"), 9),
    ]
    for y0, y1, nm, ag, oc in [
        (288.07, 301.30, g("FatherName"),   g("FatherAge"),   g("FatherQualificationOccupation")),
        (301.30, 314.50, g("MotherName"),   g("MotherAge"),   g("MotherQualificationOccupation")),
        (314.50, 327.46, g("Sibling1Name"), g("Sibling1Age"), g("Sibling1QualificationOccupation")),
        (327.46, 340.66, g("Sibling2Name"), g("Sibling2Age"), g("Sibling2QualificationOccupation")),
        (340.66, 353.62, "", "", ""),
    ]:
        p5 += [(NX, cy(y0, y1), nm, 9), (AX, cy(y0, y1), ag, 9), (OX, cy(y0, y1), oc, 9)]

    p5.append((73,  cy(380.98, 393.46), g("HobbiesInterest"),       9))
    p5 += [
        (153, cy(456.12, 481.82), g("CoCurricularActivities"), 8.5),
        (350, cy(456.12, 481.82), g("Achievements"),           8.5),
    ]

    # ── PAGE 5 · Academic Progress (Page 3 of 3) ─────────────────────────────
    # CGPA x=193  Grade x=310  Remarks x=426
    # Sem1-8 rows + Consolidated row
    # Date label y=413.14–424.18 at x=97
    # Signature  y=448.66–459.70 at x=399
    CX, GX, RX = 193, 310, 426
    p6 = []
    for y0, y1, ck, gk, rk in [
        (159.89, 181.25, "Sem1CGPA", "Sem1Grade", "Sem1Remarks"),
        (181.25, 202.37, "Sem2CGPA", "Sem2Grade", "Sem2Remarks"),
        (202.37, 223.51, "Sem3CGPA", "Sem3Grade", "Sem3Remarks"),
        (223.51, 244.63, "Sem4CGPA", "Sem4Grade", "Sem4Remarks"),
        (244.63, 265.99, "Sem5CGPA", "Sem5Grade", "Sem5Remarks"),
        (265.99, 287.11, "Sem6CGPA", "Sem6Grade", "Sem6Remarks"),
        (287.11, 308.26, "Sem7CGPA", "Sem7Grade", "Sem7Remarks"),
        (308.26, 329.62, "Sem8CGPA", "Sem8Grade", "Sem8Remarks"),
        (329.62, 350.74, "ConsolidatedCGPA", "", ""),
    ]:
        p6 += [
            (CX, cy(y0, y1), g(ck), 9),
            (GX, cy(y0, y1), g(gk), 9),
            (RX, cy(y0, y1), g(rk), 9),
        ]
    p6 += [
        (97,  cy(413.14, 424.18), today,                                          9),
        (399, cy(448.66, 459.70), g("StudentSignatureName") or g("student_name"), 9),
    ]

    # ── merge all layers ──────────────────────────────────────────────────────
    layers = {
        0: make_layer(p1),  # Cover
        1: make_layer(p2),  # Mentor Information
        3: make_layer(p4),  # Student Details
        4: make_layer(p5),  # Educational + Family
        5: make_layer(p6),  # Academic Progress
    }
    base   = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for i, page in enumerate(base.pages):
        if i in layers:
            page.merge_page(layers[i].pages[0])
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  HTTP REQUEST HANDLER
# ══════════════════════════════════════════════════════════════════════════════
class Handler(BaseHTTPRequestHandler):

    def log_message(self, *a): pass   # silence access log

    # ── helpers ───────────────────────────────────────────────────────────────
    def jsend(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def serve_file(self, path, mime):
        try:
            data = open(path, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404); self.end_headers()

    def find_student(self, prn):
        db = STATE["students"]
        s  = db.get(prn)
        if not s: s = db.get(prn.rstrip(".0"))
        if not s:
            try:
                n = float(prn)
                for k, v in db.items():
                    try:
                        if float(k) == n: s = v; break
                    except Exception: pass
            except Exception: pass
        if not s:
            lo = prn.lower()
            for k, v in db.items():
                if k.lower() == lo: s = v; break
        return s

    # ── GET ───────────────────────────────────────────────────────────────────
    def do_GET(self):
        p = urlparse(self.path)

        # Static files
        if p.path == "/" or p.path == "/index.html":
            self.serve_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
            return

        ext_map = {".css": "text/css", ".js": "application/javascript",
                   ".png": "image/png", ".ico": "image/x-icon"}
        for ext, mime in ext_map.items():
            if p.path.endswith(ext):
                fname = os.path.basename(p.path)
                self.serve_file(os.path.join(STATIC_DIR, fname), mime)
                return

        # API endpoints
        if p.path == "/api/coordinator":
            self.jsend({"ok": True, "data": load_coordinator()})

        elif p.path == "/healthz":
            self.jsend({"ok": True})

        elif p.path == "/api/lookup":
            raw = parse_qs(p.query).get("prn", [""])[0].strip()
            st  = self.find_student(raw)
            if st:
                self.jsend({
                    "ok":        True,
                    "name":      str(st.get("student_name", "")),
                    "dept":      str(st.get("DepartmentName", "")),
                    "programme": str(st.get("Programme", "")),
                    "prn":       raw,
                    "data":      {k: str(v) for k, v in st.items()
                                  if str(v) not in ("nan", "None", "NaT", "")},
                })
            else:
                avail = ", ".join(list(STATE["students"].keys())[:6])
                self.jsend({"ok": False,
                    "error": f'PRN "{raw}" not found. '
                             f'Available PRNs in your Excel: {avail}'})

        elif p.path == "/api/generate":
            raw   = parse_qs(p.query).get("prn", [""])[0].strip()
            st    = self.find_student(raw)
            pdf   = STATE["pdf_bytes"]
            coord = load_coordinator() or None
            if not st:  self.jsend({"error": "Student not found"}, 400);  return
            if not pdf: self.jsend({"error": "FAS PDF not uploaded"}, 400); return
            try:
                filled = fill_fas_form(st, pdf, coord)
                fname  = str(st.get("student_name", raw)).replace(" ", "_")
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="FAS_{fname}.pdf"')
                self.send_header("Content-Length", str(len(filled)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(filled)
            except Exception as e:
                import traceback; traceback.print_exc()
                self.jsend({"error": str(e)}, 500)

        else:
            self.send_response(404); self.end_headers()

    # ── POST ──────────────────────────────────────────────────────────────────
    def do_POST(self):

        if self.path == "/api/coordinator/save":
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))
            save_coordinator(body)
            self.jsend({"ok": True})

        elif self.path == "/api/coordinator/clear":
            clear_coordinator()
            self.jsend({"ok": True})

        elif self.path == "/api/upload":
            import cgi
            ct, pd_ = cgi.parse_header(self.headers.get("Content-Type", ""))
            pd_["boundary"]       = bytes(pd_.get("boundary", ""), "utf-8")
            pd_["CONTENT-LENGTH"] = int(self.headers.get("Content-Length", 0))
            fields = cgi.parse_multipart(self.rfile, pd_)
            ftype  = fields.get("type", [""])[0]
            fdata  = bytes(fields.get("file", [b""])[0])

            if ftype == "excel":
                try:
                    is_csv = not fdata.startswith(b"PK")
                    df = (pd.read_csv(io.BytesIO(fdata), dtype=str) if is_csv
                          else pd.read_excel(io.BytesIO(fdata), dtype=str))
                    df.columns = [c.strip() for c in df.columns]
                    df = df.fillna("")
                    prn_col = (
                        next((c for c in df.columns if c.lower().strip() == "prn"), None)
                        or next((c for c in df.columns if "prn" in c.lower()), None)
                        or df.columns[0])
                    students = {}
                    for _, row in df.iterrows():
                        key = str(row[prn_col]).strip().rstrip(".0")
                        if key and key not in ("nan", ""):
                            students[key] = row.to_dict()
                    STATE["students"] = students
                    self.jsend({"ok": True, "count": len(students),
                                "cols": len(df.columns), "prn_col": prn_col,
                                "sample": ", ".join(list(students.keys())[:5])})
                except Exception as e:
                    self.jsend({"ok": False, "error": str(e)})

            elif ftype == "pdf":
                try:
                    STATE["pdf_bytes"] = fdata
                    pages = len(PdfReader(io.BytesIO(fdata)).pages)
                    self.jsend({"ok": True, "pages": pages})
                except Exception as e:
                    self.jsend({"ok": False, "error": str(e)})
            else:
                self.jsend({"ok": False, "error": "Unknown upload type"})

        else:
            self.send_response(404); self.end_headers()


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
PORT = int(os.environ.get("PORT", "8765"))
HOST = os.environ.get("HOST", "127.0.0.1")
OPEN_BROWSER = os.environ.get("OPEN_BROWSER", "1").lower() in ("1", "true", "yes")
IS_LOCAL_DEV = HOST in ("127.0.0.1", "localhost")
DISPLAY_URL = f"http://localhost:{PORT}" if IS_LOCAL_DEV else f"http://{HOST}:{PORT}"

if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"""
╔══════════════════════════════════════════════════════╗
║   Sandip University — FAS Form Auto-Filler  v2.0    ║
╚══════════════════════════════════════════════════════╝

  ✅  http://localhost:{PORT}
  🌐  Opening browser...
  ⏹   Ctrl+C to stop

  Steps:
  1. Go to "Coordinator" tab → enter your details → Save
  2. Upload student Excel (.xlsx)
  3. Upload blank FAS PDF (.pdf)
  4. Enter PRN → Generate → PDF downloads instantly

  Coordinator profile is saved in data/coordinator.json
  and persists across restarts until you unsave it.
""")
    if OPEN_BROWSER and IS_LOCAL_DEV:
        threading.Timer(1.2, lambda: webbrowser.open(DISPLAY_URL)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✋  Server stopped.")
