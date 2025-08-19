# app.py
import os
import csv
import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from flask import (
    Flask, render_template_string, request, redirect, url_for,
    session, send_file, flash
)

# =================== CONFIG ===================
TZ = ZoneInfo("America/Los_Angeles")
DATA_JSON = "schedules.json"     # primary storage
CSV_EXPORT = "schedules_export.csv"
CLOSED_MIN = 15                  # first/last N minutes closed during class
ADMIN_PIN = os.getenv("BATHROOM_ADMIN_PIN", "1234")  # change me (env var)
SECRET = os.getenv("BATHROOM_SECRET_KEY", "change-me")  # Flask session key
PORT = int(os.getenv("PORT", "5050"))  # default 5050 to avoid AirPlay on macOS

app = Flask(__name__)
app.secret_key = SECRET

# =================== DEFAULT SCHEDULES ===================
# Stored as {"monday":[...], "tue-fri":[...]} rows:
# {"label": "Period 2", "is_class": 1, "start": "08:10", "end": "08:48"}
DEFAULT_SCHEDULES = {
    "monday": [
        {"label": "Period 2", "is_class": 1, "start": "08:10", "end": "08:48"},
        {"label": "Period 3", "is_class": 1, "start": "08:52", "end": "09:30"},
        {"label": "Nutrition Break", "is_class": 0, "start": "09:30", "end": "09:38"},
        {"label": "Period 4", "is_class": 1, "start": "09:40", "end": "10:18"},
        {"label": "Period 5", "is_class": 1, "start": "10:22", "end": "11:00"},
        {"label": "Lunch", "is_class": 0, "start": "11:05", "end": "11:35"},
        {"label": "Period 6", "is_class": 1, "start": "11:40", "end": "12:18"},
        {"label": "Period 7", "is_class": 1, "start": "12:22", "end": "13:00"},
    ],
    "tue-fri": [
        {"label": "Study Skills/ELD", "is_class": 1, "start": "08:10", "end": "08:40"},
        {"label": "Period 2",         "is_class": 1, "start": "08:45", "end": "09:35"},
        {"label": "Period 3",         "is_class": 1, "start": "09:40", "end": "10:30"},
        {"label": "Nutrition Break",  "is_class": 0, "start": "10:35", "end": "10:40"},
        {"label": "Period 4",         "is_class": 1, "start": "10:45", "end": "11:35"},
        {"label": "Period 5",         "is_class": 1, "start": "11:40", "end": "12:30"},
        {"label": "Lunch",            "is_class": 0, "start": "12:35", "end": "13:05"},
        {"label": "Period 6",         "is_class": 1, "start": "13:10", "end": "14:00"},
        {"label": "Period 7",         "is_class": 1, "start": "14:05", "end": "14:55"},
    ]
}

DAY_KEYS = ["monday", "tue-fri"]  # Monday modified, Tue–Fri regular
WEEKDAY_TO_KEY = {0: "monday", 1: "tue-fri", 2: "tue-fri", 3: "tue-fri", 4: "tue-fri"}

# =================== STORAGE ===================
def load_schedules():
    if not os.path.exists(DATA_JSON):
        save_schedules(DEFAULT_SCHEDULES)
        return DEFAULT_SCHEDULES
    with open(DATA_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def save_schedules(data):
    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def parse_hhmm(s):
    h, m = s.split(":")
    return time(int(h), int(m))

def as_dt(now_date, t):
    return datetime.combine(now_date, t, tzinfo=TZ)

# =================== CORE LOGIC ===================
def today_schedule(now, schedules):
    key = WEEKDAY_TO_KEY.get(now.weekday())
    if not key:
        return []
    # Convert to list of tuples with parsed times
    rows = []
    for r in schedules.get(key, []):
        rows.append((r["label"], bool(int(r["is_class"])), parse_hhmm(r["start"]), parse_hhmm(r["end"])))
    return rows

def compute_open_windows_for_today(now, schedules):
    sched = today_schedule(now, schedules)
    if not sched:
        return []
    open_blocks = []

    def add_block(s_dt, e_dt, label):
        if e_dt > s_dt:
            open_blocks.append((s_dt, e_dt, label))

    for i, (label, is_class, s, e) in enumerate(sched):
        s_dt, e_dt = as_dt(now.date(), s), as_dt(now.date(), e)
        if is_class:
            add_block(s_dt + timedelta(minutes=CLOSED_MIN),
                      e_dt - timedelta(minutes=CLOSED_MIN),
                      f"{label} (middle of class)")
        else:
            add_block(s_dt, e_dt, label)

        if i < len(sched) - 1:
            next_s = as_dt(now.date(), sched[i+1][2])
            add_block(e_dt, next_s, "Passing time")

    return sorted(open_blocks, key=lambda x: x[0])

def current_status(now, schedules):
    sched = today_schedule(now, schedules)
    if not sched:
        return ("OUTSIDE", "No school today", None)

    blocks = []
    for label, is_class, s, e in sched:
        s_dt, e_dt = as_dt(now.date(), s), as_dt(now.date(), e)
        blocks.append((label, is_class, s_dt, e_dt))

    day_start = blocks[0][2]
    day_end = blocks[-1][3]

    if now < day_start:
        return ("OUTSIDE", "Before school hours", day_start)
    if now >= day_end:
        return ("OUTSIDE", "After school hours", None)

    for (label, is_class, s_dt, e_dt) in blocks:
        if s_dt <= now < e_dt:
            if is_class:
                if now < s_dt + timedelta(minutes=CLOSED_MIN):
                    return ("CLOSED", f"{label}: first {CLOSED_MIN} min", s_dt + timedelta(minutes=CLOSED_MIN))
                if now >= e_dt - timedelta(minutes=CLOSED_MIN):
                    return ("CLOSED", f"{label}: last {CLOSED_MIN} min", e_dt)
                return ("OPEN", f"{label}: middle of class", e_dt - timedelta(minutes=CLOSED_MIN))
            else:
                return ("OPEN", f"{label}", e_dt)

    for (label, is_class, s_dt, e_dt) in blocks:
        if now < s_dt:
            return ("OPEN", "Passing time", s_dt)

    return ("OPEN", "Passing time", None)

# =================== TEMPLATES ===================
DASHBOARD_HTML = """
<!doctype html>
<html><head>
<meta charset="utf-8" />
<title>MTM Bathroom Status</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  html,body{margin:0;background:#0b0f14;color:#eaeff7;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial}
  .wrap{max-width:1000px;margin:0 auto;padding:24px}
  .clock{font-size:clamp(28px,6vw,54px);font-weight:700;opacity:.9}
  .status{margin-top:8px;font-size:clamp(38px,10vw,92px);font-weight:900}
  .open{color:#3ddc84}.closed{color:#ff5c5c}.outside{color:#9aa4b2}
  .reason{margin-top:6px;font-size:clamp(16px,2.8vw,22px);color:#b5c0cd}
  .next{margin-top:2px;font-size:clamp(14px,2.4vw,18px);color:#93a1af}
  table{width:100%;border-collapse:collapse;margin-top:18px;background:#121821;border:1px solid #223040;border-radius:10px;overflow:hidden}
  th,td{padding:12px 14px;border-bottom:1px solid #223040} th{text-align:left;background:#152030;color:#bcd0e5}
  tr:last-child td{border-bottom:none}
  .pill{padding:2px 8px;border-radius:999px;font-size:12px;background:#1b2533;color:#a9b8c7}
  .footer{margin-top:14px;font-size:12px;color:#7f8b97}
  .topbar{display:flex;justify-content:space-between;align-items:center}
  a.link{color:#9ecbff;text-decoration:none}
</style>
<script>setInterval(()=>location.reload(),30000);</script>
</head><body>
<div class="wrap">
  <div class="topbar">
    <div class="clock">{{ now_fmt }}</div>
    <div><a class="link" href="{{ url_for('admin_login') }}">Admin</a></div>
  </div>
  <div class="status {{ status|lower }}">{{ status }}</div>
  <div class="reason">{{ reason }}</div>
  {% if next_change %}
    <div class="next">Next change: {{ next_change }}</div>
  {% endif %}

  <table>
    <tr><th>Open From</th><th>Until</th><th>Context</th></tr>
    {% for s,e,label in open_blocks %}
      <tr>
        <td>{{ s.strftime("%-I:%M %p") }}</td>
        <td>{{ e.strftime("%-I:%M %p") }}</td>
        <td><span class="pill">{{ label }}</span></td>
      </tr>
    {% endfor %}
  </table>

  <div class="footer">Rule: Bathrooms are CLOSED the first and last {{ closed_min }} minutes of any class. All other times are OPEN.</div>
</div>
</body></html>
"""

ADMIN_LOGIN_HTML = """
<!doctype html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin Login</title>
<style>
  body{background:#0b0f14;color:#eaeff7;font-family:system-ui;-apple-system,Segoe UI,Roboto,Arial}
  .wrap{max-width:420px;margin:10vh auto;padding:24px;background:#121821;border:1px solid #223040;border-radius:10px}
  label{display:block;margin-bottom:8px}
  input[type=password],input[type=text]{width:100%;padding:12px;border:1px solid #223040;border-radius:8px;background:#0e141c;color:#eaeff7}
  button{margin-top:12px;padding:12px 16px;border-radius:10px;border:none;background:#3b82f6;color:white;font-weight:700;cursor:pointer}
  a{color:#9ecbff;text-decoration:none}
  .msg{color:#ff9b9b;margin-top:10px}
</style>
</head><body><div class="wrap">
  <h2>Admin Login</h2>
  <form method="post">
    <label>PIN
      <input name="pin" type="password" autocomplete="current-password" placeholder="Enter PIN" required>
    </label>
    <button type="submit">Log in</button>
  </form>
  {% if msg %}<div class="msg">{{ msg }}</div>{% endif %}
  <p><a href="{{ url_for('index') }}">Back to Dashboard</a></p>
</div></body></html>
"""

ADMIN_SCHEDULE_HTML = """
<!doctype html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Edit Schedule</title>
<style>
  body{background:#0b0f14;color:#eaeff7;font-family:system-ui;-apple-system,Segoe UI,Roboto,Arial}
  .wrap{max-width:1100px;margin:4vh auto;padding:24px}
  table{width:100%;border-collapse:collapse;background:#121821;border:1px solid #223040;border-radius:10px;overflow:hidden}
  th,td{padding:10px 12px;border-bottom:1px solid #223040}
  th{background:#152030;color:#bcd0e5;text-align:left}
  input[type=text]{width:100%;padding:8px;border:1px solid #223040;border-radius:8px;background:#0e141c;color:#eaeff7}
  select{padding:8px;border:1px solid #223040;border-radius:8px;background:#0e141c;color:#eaeff7}
  button.primary{padding:10px 14px;border:none;border-radius:10px;background:#3ddc84;color:#0b0f14;font-weight:800;cursor:pointer}
  button.warn{padding:8px 12px;border:none;border-radius:8px;background:#ff5c5c;color:white;cursor:pointer}
  .row-actions{white-space:nowrap}
  .bar{display:flex;gap:10px;align-items:center;justify-content:space-between;margin-bottom:12px}
  a{color:#9ecbff;text-decoration:none}
  .pill{padding:2px 8px;border-radius:999px;font-size:12px;background:#1b2533;color:#a9b8c7}
</style>
</head><body><div class="wrap">
  <div class="bar">
    <div>
      <a href="{{ url_for('index') }}">⟵ Dashboard</a>
      <span class="pill">Closed-min: {{ closed_min }}</span>
    </div>
    <div style="display:flex;gap:8px;">
      <a href="{{ url_for('download_csv') }}">Export CSV</a>
      <form method="post" action="{{ url_for('upload_csv') }}" enctype="multipart/form-data" style="display:inline">
        <input type="file" name="file" accept=".csv" required>
        <button class="primary" type="submit">Upload CSV</button>
      </form>
    </div>
  </div>

  <form method="post">
    {% for key in day_keys %}
      <h3 style="margin:6px 0 8px 2px;">{{ 'Monday (Modified)' if key=='monday' else 'Tuesday–Friday' }}</h3>
      <table>
        <tr><th>Label</th><th>Is Class?</th><th>Start (HH:MM)</th><th>End (HH:MM)</th><th class="row-actions">Actions</th></tr>
        {% for row in schedules[key] %}
            {% set i = loop.index0 %}
             <tr>
                <td><input type="text" name="{{ key }}__label__{{ i }}" value="{{ row['label'] }}"></td>
                <td>
                    <select name="{{ key }}__is_class__{{ i }}">
                        <option value="1" {% if row['is_class']|int==1 %}selected{% endif %}>Yes</option>
                        <option value="0" {% if row['is_class']|int==0 %}selected{% endif %}>No</option>
                    </select>
                </td>
                <td><input type="text" name="{{ key }}__start__{{ i }}" value="{{ row['start'] }}" placeholder="08:10"></td>
                <td><input type="text" name="{{ key }}__end__{{ i }}" value="{{ row['end'] }}" placeholder="08:48"></td>
                <td class="row-actions"><button class="warn" name="delete" value="{{ key }}__{{ i }}">Delete</button></td>
            </tr>
        {% endfor %}
        <tr>
          <td><input type="text" name="{{ key }}__new__label" placeholder="New block label"></td>
          <td>
            <select name="{{ key }}__new__is_class"><option value="1">Yes</option><option value="0">No</option></select>
          </td>
          <td><input type="text" name="{{ key }}__new__start" placeholder="HH:MM"></td>
          <td><input type="text" name="{{ key }}__new__end" placeholder="HH:MM"></td>
          <td></td>
        </tr>
      </table>
      <br/>
    {% endfor %}
    <button class="primary" type="submit">Save Changes</button>
  </form>
</div></body></html>
"""

# =================== ROUTES ===================
@app.route("/")
def index():
    schedules = load_schedules()
    now = datetime.now(TZ)
    status, reason, next_dt = current_status(now, schedules)
    opens = compute_open_windows_for_today(now, schedules)
    return render_template_string(
        DASHBOARD_HTML,
        now_fmt=now.strftime("%A, %B %-d • %-I:%M %p"),
        status=status, reason=reason,
        next_change=next_dt.strftime("%-I:%M %p") if next_dt else None,
        open_blocks=opens, closed_min=CLOSED_MIN
    )

# -------- Admin Auth --------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pin = request.form.get("pin", "")
        if pin == ADMIN_PIN:
            session["admin"] = True
            return redirect(url_for("admin_schedule"))
        return render_template_string(ADMIN_LOGIN_HTML, msg="Incorrect PIN")
    return render_template_string(ADMIN_LOGIN_HTML, msg=None)

def require_admin():
    return session.get("admin") == True

# -------- Schedule Editor --------
@app.route("/admin/schedule", methods=["GET", "POST"])
def admin_schedule():
    if not require_admin():
        return redirect(url_for("admin_login"))

    schedules = load_schedules()

    if request.method == "POST":
        # Delete row?
        delete = request.form.get("delete")
        if delete:
            key, idx = delete.split("__")
            idx = int(idx)
            if key in schedules and 0 <= idx < len(schedules[key]):
                schedules[key].pop(idx)
                save_schedules(schedules)
            return redirect(url_for("admin_schedule"))

        # Update existing rows
        for key in DAY_KEYS:
            for i in range(len(schedules[key])):
                schedules[key][i]["label"] = request.form.get(f"{key}__label__{i}", schedules[key][i]["label"])
                schedules[key][i]["is_class"] = int(request.form.get(f"{key}__is_class__{i}", schedules[key][i]["is_class"]))
                schedules[key][i]["start"] = request.form.get(f"{key}__start__{i}", schedules[key][i]["start"])
                schedules[key][i]["end"]   = request.form.get(f"{key}__end__{i}", schedules[key][i]["end"])

        # Add new rows (if provided)
        for key in DAY_KEYS:
            nlabel = request.form.get(f"{key}__new__label", "").strip()
            nstart = request.form.get(f"{key}__new__start", "").strip()
            nend   = request.form.get(f"{key}__new__end", "").strip()
            niscl  = request.form.get(f"{key}__new__is_class", "1").strip()
            if nlabel and nstart and nend:
                schedules[key].append({"label": nlabel, "is_class": int(niscl), "start": nstart, "end": nend})

        save_schedules(schedules)
        return redirect(url_for("admin_schedule"))

    return render_template_string(
        ADMIN_SCHEDULE_HTML,
        schedules=schedules, day_keys=DAY_KEYS, closed_min=CLOSED_MIN
    )

# -------- CSV Import/Export --------
@app.route("/admin/download")
def download_csv():
    if not require_admin():
        return redirect(url_for("admin_login"))
    schedules = load_schedules()
    with open(CSV_EXPORT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["day","label","is_class","start","end"])
        for day in DAY_KEYS:
            for r in schedules.get(day, []):
                w.writerow([day, r["label"], int(r["is_class"]), r["start"], r["end"]])
    return send_file(CSV_EXPORT, as_attachment=True)

@app.route("/admin/upload", methods=["POST"])
def upload_csv():
    if not require_admin():
        return redirect(url_for("admin_login"))
    file = request.files.get("file")
    if not file or not file.filename.lower().endswith(".csv"):
        flash("Please upload a CSV file.")
        return redirect(url_for("admin_schedule"))
    content = file.read().decode("utf-8").splitlines()
    reader = csv.DictReader(content)
    new_sched = {k: [] for k in DAY_KEYS}
    for row in reader:
        day = (row.get("day","") or "").strip().lower()
        if day not in DAY_KEYS:  # ignore unknown day keys
            continue
        new_sched[day].append({
            "label": (row.get("label","") or "").strip(),
            "is_class": int((row.get("is_class","1") or "1").strip()),
            "start": (row.get("start","") or "").strip(),
            "end": (row.get("end","") or "").strip()
        })
    save_schedules(new_sched)
    return redirect(url_for("admin_schedule"))

# =================== MAIN ===================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)

