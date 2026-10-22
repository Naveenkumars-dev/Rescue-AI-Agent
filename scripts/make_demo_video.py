"""
RescueFlow AI — Demo Video Generator
Creates submission/video/demo.mp4 using real Strands Decider 2B decisions.

Generates a ~2:30 min MP4 showing:
  0:00  Title card + tagline
  0:08  Problem slide
  0:18  Architecture slide  
  0:30  Incident A (Flood) — LIVE Strands Decider 2B: BLOCK/CRITICAL
  1:00  Incident B (Road) — LIVE Strands Decider 2B: REVIEW/HIGH
  1:25  Incident C (Power) — LIVE Strands Decider 2B: REVIEW/MEDIUM
  1:50  Decision Arena — priority order of all three
  2:15  Reassessment — condition change on Incident A
  2:35  End card

Usage: SSL_CERT_FILE=... .venv/bin/python scripts/make_demo_video.py
"""
from __future__ import annotations
import json, os, subprocess, sys, textwrap, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "submission" / "video"
OUT.mkdir(parents=True, exist_ok=True)
TMP = OUT / "frames"
TMP.mkdir(parents=True, exist_ok=True)

W, H = 1280, 720

# ── Colours ────────────────────────────────────────────────────────────────────
BG      = (11, 16, 32)
PANEL   = (18, 26, 46)
BORDER  = (34, 48, 82)
WHITE   = (231, 236, 246)
MUTE    = (141, 154, 181)
ORANGE  = (255, 153, 0)
GREEN   = (52, 211, 153)
RED     = (248, 113, 113)
AMBER   = (251, 191, 36)
BLUE    = (96, 165, 250)

from PIL import Image, ImageDraw, ImageFont

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Try system fonts, fall back to default."""
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
        "/System/Library/Fonts/SFCompactText.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default(size=size)

def new_frame() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)

def rect(d: ImageDraw.ImageDraw, x1: int, y1: int, x2: int, y2: int,
         fill=PANEL, outline=BORDER, radius: int = 12) -> None:
    d.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline, width=1)

def text(d: ImageDraw.ImageDraw, x: int, y: int, s: str,
         size: int = 18, color=WHITE, bold: bool = False,
         anchor: str = "la") -> int:
    f = _font(size, bold)
    d.text((x, y), s, font=f, fill=color, anchor=anchor)
    # estimate height
    try: return int(f.getbbox(s)[3] - f.getbbox(s)[1]) + 6
    except: return size + 6

def wrap_text(d: ImageDraw.ImageDraw, x: int, y: int, s: str,
              size: int = 16, color=WHITE, width: int = 60) -> int:
    lines = textwrap.wrap(s, width=width)
    f = _font(size)
    lh = size + 8
    for ln in lines:
        d.text((x, y), ln, font=f, fill=color, anchor="la")
        y += lh
    return y

def dot(d: ImageDraw.ImageDraw, x: int, y: int, c=ORANGE) -> None:
    d.ellipse([x-5, y-5, x+5, y+5], fill=c)

def prob_bar(d: ImageDraw.ImageDraw, x: int, y: int, label: str, p: float, w: int = 280) -> None:
    f16 = _font(14)
    d.text((x, y+2), label, font=f16, fill=MUTE, anchor="la")
    bx = x + 150
    d.rounded_rectangle([bx, y+4, bx+w, y+16], radius=4, fill=BORDER)
    fill_c = GREEN if p >= 0.5 else RED
    bar_w = int(p * w)
    if bar_w > 4:
        d.rounded_rectangle([bx, y+4, bx+bar_w, y+16], radius=4, fill=fill_c)
    d.text((bx+w+8, y+2), f"{p:.2f}", font=f16, fill=MUTE, anchor="la")

def verdict_badge(d: ImageDraw.ImageDraw, x: int, y: int, verdict: str) -> None:
    colors = {"block": RED, "review": AMBER, "allow": GREEN}
    labels = {"block": "BLOCK / ESCALATE", "review": "REVIEW", "allow": "ALLOW"}
    c = colors.get(verdict, MUTE)
    lbl = labels.get(verdict, verdict.upper())
    f = _font(14, bold=True)
    bbox = d.textbbox((0, 0), lbl, font=f)
    pw = bbox[2] - bbox[0] + 24
    ph = 26
    d.rounded_rectangle([x, y, x+pw, y+ph], radius=6, fill=(*c[:3], 40) if len(c)==3 else c,
                         outline=c, width=2)
    d.text((x + pw//2, y + ph//2), lbl, font=f, fill=c, anchor="mm")

def header(d: ImageDraw.ImageDraw, title: str = "RescueFlow AI") -> None:
    dot(d, 24, 28, ORANGE)
    text(d, 40, 18, title, size=18, bold=True, color=WHITE)
    text(d, 40, 40, "Emergency Response Decision Support  ·  PROTOTYPE — not for real dispatch",
         size=13, color=MUTE)
    d.line([0, 58, W, 58], fill=BORDER, width=1)

def footer(d: ImageDraw.ImageDraw) -> None:
    d.line([0, H-36, W, H-36], fill=BORDER, width=1)
    text(d, W//2, H-22, "Built with the AWS User Group Madurai Strands Decider hackathon kit  ·  #strands-decider-2b  ·  #policy",
         size=12, color=MUTE, anchor="mm")

def save_png(img: Image.Image, name: str) -> Path:
    p = TMP / f"{name}.png"
    img.save(p)
    return p

# ── Fetch live decisions from running server ───────────────────────────────────

def api(path: str, method: str = "GET", body: dict | None = None) -> dict:
    url = f"http://127.0.0.1:8501{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())

# ── Frame builders ─────────────────────────────────────────────────────────────

def frame_title() -> Path:
    img, d = new_frame()
    # glow dot
    for r in range(80, 0, -10):
        alpha = int(255 * (1 - r/80) * 0.3)
        d.ellipse([W//2-r, 200-r, W//2+r, 200+r], fill=(255,153,0))
    dot(d, W//2, 200, ORANGE)
    text(d, W//2, 240, "RescueFlow AI", size=64, bold=True, color=WHITE, anchor="mm")
    text(d, W//2, 310, '"An agent that decides what needs attention first."', size=24, color=MUTE, anchor="mm")
    text(d, W//2, 360, "Strands Decider 2B  ·  Amazon Bedrock  ·  #policy", size=18, color=ORANGE, anchor="mm")
    # feature bullets
    feats = [
        "Reads incident reports in plain language",
        "Strands Decider 2B classifies: allow / review / BLOCK",
        "Life-safety incidents are escalated, never auto-dispatched",
        "Decision Arena: compare competing incidents live",
    ]
    y = 420
    for f in feats:
        dot(d, W//2 - 240, y+8, GREEN)
        text(d, W//2 - 220, y, f, size=17, color=WHITE)
        y += 34
    footer(d)
    return save_png(img, "00_title")

def frame_problem() -> Path:
    img, d = new_frame()
    header(d)
    text(d, W//2, 100, "The Problem", size=36, bold=True, anchor="mm")
    problems = [
        ("🌊", "Multiple incidents at once", "Which one needs attention first?"),
        ("⚖️", "Competing priorities",        "Flood vs. road block vs. power outage"),
        ("❓", "Missing information",          "Trapped? How many? Resources available?"),
        ("🧠", "Needs language reading",       "Not just numbers — context, urgency, uncertainty"),
    ]
    y = 160
    for icon, title, sub in problems:
        rect(d, 80, y, W-80, y+70, fill=PANEL, outline=BORDER)
        text(d, 110, y+10, icon, size=30, anchor="la")
        text(d, 160, y+8, title, size=20, bold=True, color=WHITE)
        text(d, 160, y+36, sub, size=15, color=MUTE)
        y += 88
    footer(d)
    return save_png(img, "01_problem")

def frame_architecture() -> Path:
    img, d = new_frame()
    header(d)
    text(d, W//2, 90, "How RescueFlow AI Works", size=32, bold=True, anchor="mm")

    components = [
        (100, 180, 280, 260, "React Dashboard", "Incidents · Arena · Decisions", ORANGE),
        (340, 180, 560, 260, "FastAPI Backend", "12 REST endpoints", BLUE),
        (600, 180, 820, 260, "Strands Agent", "LLM + 13 Tools", GREEN),
        (860, 180, 1090, 260, "Strands Decider 2B", "allow / review / BLOCK", RED),
        (340, 340, 820, 420, "agent/decision.py  (#policy)", "build_state → TriagePolicy → verdict", AMBER),
        (100, 500, 560, 580, "Seeded Data (mock)", "10 incidents · 8 resource types", MUTE),
        (600, 500, 1090, 580, "Amazon Bedrock AgentCore Runtime", "deployment target", ORANGE),
    ]
    arrows = [
        (280, 220, 340, 220),
        (560, 220, 600, 220),
        (820, 220, 860, 220),
        (690, 260, 690, 340),
        (340, 380, 340, 500),
        (690, 420, 690, 500),
    ]
    for x1, y1, x2, y2, title, sub, c in components:
        rect(d, x1, y1, x2, y2, fill=PANEL, outline=c)
        text(d, (x1+x2)//2, y1+18, title, size=14, bold=True, color=c, anchor="mm")
        text(d, (x1+x2)//2, y1+40, sub, size=12, color=MUTE, anchor="mm")
    for x1, y1, x2, y2 in arrows:
        d.line([x1, y1, x2, y2], fill=BORDER, width=2)
        d.polygon([(x2, y2), (x2-6, y2-4), (x2-6, y2+4)], fill=BORDER)
    footer(d)
    return save_png(img, "02_architecture")

def frame_incident(inc_id: str, result: dict, pos: int, total: int) -> Path:
    img, d = new_frame()
    header(d)
    inc = result.get("incident", {})
    dec = result.get("decision", {})
    model_decs = result.get("model_decisions", [{}])
    md = model_decs[0] if model_decs else {}

    # top strip
    text(d, 30, 75, f"Incident Evaluation  ({pos}/{total})", size=14, color=MUTE)
    text(d, 30, 100, f"{inc.get('id','?')} — {inc.get('type','?').title()} at {inc.get('location','?')}",
         size=22, bold=True)

    # left: report
    rect(d, 30, 140, 580, 440)
    text(d, 50, 155, "Incident Report", size=13, color=MUTE)
    wrap_text(d, 50, 178, inc.get("report", ""), size=15, color=WHITE, width=42)
    text(d, 50, 360, f"Hazards: {inc.get('hazards','?')}", size=13, color=MUTE)
    text(d, 50, 382, f"Preliminary risk score: {result.get('preliminary_score','?')}/100", size=13, color=ORANGE)
    text(d, 50, 404, f"Resources: {(result.get('resources') or '?')[:60]}", size=13, color=MUTE)

    # right: Strands Decider 2B
    rect(d, 610, 140, W-30, 440)
    text(d, 630, 155, "Strands Decider 2B", size=13, color=ORANGE)

    verdict = md.get("verdict", dec.get("triage_verdict", "review"))
    priority = md.get("priority", "?")
    p_ls = md.get("life_safety_p_yes", 0)
    decider_ms = md.get("decider_ms", 0)

    verdict_badge(d, 630, 178, verdict)
    text(d, 630, 218, f"Priority: {priority.upper()}", size=16, bold=True, color=WHITE)

    # prob bars
    pri_probs = md.get("priority_probs", {})
    y_bar = 250
    for lvl in ["low","medium","high","critical"]:
        p = pri_probs.get(lvl, 0.0)
        prob_bar(d, 630, y_bar, f"priority: {lvl}", p)
        y_bar += 28
    prob_bar(d, 630, y_bar+5, "life_safety", p_ls)

    text(d, 630, y_bar+40, f"Decider: {decider_ms} ms  ·  1 forward pass", size=13, color=MUTE)

    # decision reason
    reason = md.get("reason", dec.get("triage_reason", ""))
    rect(d, 30, 455, W-30, 560)
    text(d, 50, 468, "Triage Reason", size=13, color=MUTE)
    wrap_text(d, 50, 490, reason[:200], size=15, color=WHITE, width=100)
    text(d, 50, 540, f"Decision status: {dec.get('decision_status','PROPOSED')}  ·  Human review: {dec.get('human_review_required','?')}",
         size=13, color=MUTE)

    footer(d)
    return save_png(img, f"03_inc_{inc_id.lower()}")

def frame_arena(arena: dict) -> Path:
    img, d = new_frame()
    header(d)
    text(d, W//2, 90, "⚔  Decision Arena — Priority Order", size=28, bold=True, anchor="mm")
    text(d, W//2, 120, "Three incidents. One Strands Decider 2B call each. Ranked automatically.", size=15, color=MUTE, anchor="mm")

    decs = arena.get("decisions", [])
    order = arena.get("priority_order") or ["INC-001","INC-002","INC-003"]
    icons = {"block":"🚨","review":"⚠️ ","allow":"✅"}
    colors_v = {"block": RED, "review": AMBER, "allow": GREEN}
    y = 155
    for pos, iid in enumerate(order[:3], 1):
        # find the decision for this incident
        dec = decs[pos-1] if pos-1 < len(decs) else {}
        verdict = dec.get("verdict","review")
        priority = dec.get("priority","?").upper()
        reason = (dec.get("reason","")[:90] + "...") if len(dec.get("reason","")) > 90 else dec.get("reason","")
        c = colors_v.get(verdict, MUTE)
        rect(d, 60, y, W-60, y+90, outline=c)
        # position badge
        text(d, 90, y+28, str(pos), size=32, bold=True, color=c)
        text(d, 130, y+10, f"{icons.get(verdict,'')} {iid} — {verdict.upper()}", size=18, bold=True, color=c)
        text(d, 130, y+38, f"Priority: {priority}  |  Decider: {dec.get('decider_ms',0)} ms", size=14, color=MUTE)
        text(d, 130, y+62, reason, size=13, color=WHITE)
        y += 108

    text(d, W//2, y+20, f"Total latency: {arena.get('latency_ms',0)} ms  ·  {len(decs)} Strands Decider 2B calls",
         size=14, color=MUTE, anchor="mm")
    footer(d)
    return save_png(img, "04_arena")

def frame_reassess(before: dict, after: dict, update_text: str) -> Path:
    img, d = new_frame()
    header(d)
    text(d, W//2, 90, "↺  Reassessment — Condition Change", size=28, bold=True, anchor="mm")
    rect(d, 60, 115, W-60, 160, fill=(60,40,10), outline=AMBER)
    text(d, W//2, 138, f"New condition: {update_text}", size=15, color=AMBER, anchor="mm")

    def dec_panel(x1: int, label: str, result: dict, title_color) -> None:
        rect(d, x1, 175, x1+540, 500, outline=title_color)
        text(d, x1+20, 185, label, size=14, color=title_color)
        dec = result.get("decision", {})
        model_decs = result.get("model_decisions", [{}])
        md = model_decs[0] if model_decs else {}
        verdict = md.get("verdict", dec.get("triage_verdict","review"))
        priority = md.get("priority","?").upper()
        p_ls = md.get("life_safety_p_yes", 0)
        decider_ms = md.get("decider_ms",0)
        verdict_badge(d, x1+20, 212, verdict)
        text(d, x1+20, 256, f"Priority: {priority}", size=18, bold=True, color=WHITE)
        pri_probs = md.get("priority_probs", {})
        yb = 288
        for lvl in ["low","medium","high","critical"]:
            prob_bar(d, x1+20, yb, f"priority: {lvl}", pri_probs.get(lvl,0), w=200)
            yb += 26
        prob_bar(d, x1+20, yb+4, "life_safety", p_ls, w=200)
        text(d, x1+20, yb+36, f"Decider: {decider_ms} ms", size=13, color=MUTE)
        reason = md.get("reason", dec.get("triage_reason",""))[:140]
        wrap_text(d, x1+20, yb+62, reason, size=13, color=MUTE, width=45)

    dec_panel(60, "BEFORE — original report", before, BLUE)
    # arrow
    text(d, W//2, 330, "→", size=40, color=ORANGE, anchor="mm")
    dec_panel(700, "AFTER — updated conditions", after, ORANGE)
    footer(d)
    return save_png(img, "05_reassess")

def frame_end() -> Path:
    img, d = new_frame()
    dot(d, W//2, 180, ORANGE)
    text(d, W//2, 220, "RescueFlow AI", size=56, bold=True, anchor="mm")
    text(d, W//2, 285, "Decision-support prototype — not for real emergency dispatch", size=17, color=MUTE, anchor="mm")

    stats = [
        ("10", "seed incidents"),
        ("3",  "typed questions per triage"),
        ("~7s", "per Strands Decider decision"),
        ("78", "automated tests passing"),
    ]
    x = 140
    for val, lbl in stats:
        rect(d, x, 330, x+220, 430)
        text(d, x+110, 358, val, size=32, bold=True, color=ORANGE, anchor="mm")
        text(d, x+110, 400, lbl, size=14, color=MUTE, anchor="mm")
        x += 250

    text(d, W//2, 460, "#strands-decider-2b  ·  #policy", size=20, color=ORANGE, anchor="mm")
    text(d, W//2, 498, "github.com/Naveenkumars-dev/Rescue-AI-Agent", size=17, color=BLUE, anchor="mm")
    text(d, W//2, 535, "Strands Decider 2B: StrandsAgents/strands-decider-2B  ·  Amazon Bedrock for the LLM", size=14, color=MUTE, anchor="mm")
    footer(d)
    return save_png(img, "06_end")

# ── Collect live data ──────────────────────────────────────────────────────────

def collect_decisions() -> dict:
    print("[video] resetting demo data...", flush=True)
    api("/api/demo/reset", "POST")
    time.sleep(0.5)

    print("[video] evaluating INC-001 (Flood)...", flush=True)
    ev1 = api("/api/incidents/INC-001/evaluate", "POST", {"context": ""})

    print("[video] evaluating INC-002 (Road obstruction)...", flush=True)
    ev2 = api("/api/incidents/INC-002/evaluate", "POST", {"context": ""})

    print("[video] evaluating INC-003 (Power outage)...", flush=True)
    ev3 = api("/api/incidents/INC-003/evaluate", "POST", {"context": ""})

    print("[video] running Decision Arena...", flush=True)
    arena = api("/api/decisions/evaluate", "POST", {"incident_ids": ["INC-001","INC-002","INC-003"]})

    update = "Resident confirmed trapped on first floor. Water now at chest height."
    print(f"[video] reassessing INC-001 with: {update[:50]}...", flush=True)
    ev1_after = api(f"/api/incidents/INC-001/reassess", "POST", {"update": update})

    return {"ev1": ev1, "ev2": ev2, "ev3": ev3, "arena": arena,
            "ev1_after": ev1_after, "update": update}

# ── Build video from frames ────────────────────────────────────────────────────

def build_video(frames: list[tuple[Path, float]]) -> Path:
    """frames: list of (png_path, duration_seconds). Returns output mp4."""
    # Write a file list for ffmpeg concat
    concat = TMP / "concat.txt"
    with open(concat, "w") as f:
        for png, dur in frames:
            f.write(f"file '{png.absolute()}'\n")
            f.write(f"duration {dur:.2f}\n")
        # repeat last frame (ffmpeg concat needs duration on last)
        if frames:
            f.write(f"file '{frames[-1][0].absolute()}'\n")

    out = OUT / "demo.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat),
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black",
        "-r", "25",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "23", "-preset", "fast",
        str(out)
    ]
    print(f"[video] assembling {len(frames)} slides into MP4...", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ffmpeg stderr:", result.stderr[-500:])
        raise RuntimeError("ffmpeg failed")
    size_mb = out.stat().st_size / 1e6
    # get duration
    probe = subprocess.run(
        ["ffprobe","-v","quiet","-show_entries","format=duration","-of","csv=p=0",str(out)],
        capture_output=True, text=True)
    dur_s = float(probe.stdout.strip() or "0")
    print(f"[video] done: {out}  ({size_mb:.1f} MB, {dur_s:.0f}s)", flush=True)
    return out

def save_run_json(data: dict) -> None:
    run = {
        "created_at": time.strftime("%Y-%m-%d %H:%M"),
        "inc_001_verdict": (data["ev1"].get("model_decisions") or [{}])[0].get("verdict","?"),
        "inc_001_priority": (data["ev1"].get("model_decisions") or [{}])[0].get("priority","?"),
        "inc_001_life_safety_p": (data["ev1"].get("model_decisions") or [{}])[0].get("life_safety_p_yes","?"),
        "inc_002_verdict": (data["ev2"].get("model_decisions") or [{}])[0].get("verdict","?"),
        "inc_003_verdict": (data["ev3"].get("model_decisions") or [{}])[0].get("verdict","?"),
        "arena_order": data["arena"].get("incidents_compared") or data["arena"].get("priority_order"),
        "arena_latency_ms": data["arena"].get("latency_ms"),
        "reassess_verdict": (data["ev1_after"].get("model_decisions") or [{}])[0].get("verdict","?"),
    }
    (OUT / "run.json").write_text(json.dumps(run, indent=2))
    print("[video] run.json saved", flush=True)

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("RescueFlow AI — Demo Video Generator")
    print("=" * 60)

    print("[video] collecting live decisions from Strands Decider 2B...")
    data = collect_decisions()
    save_run_json(data)

    print("[video] generating frames...")
    frames: list[tuple[Path, float]] = []

    def add(f: Path, dur: float) -> None:
        frames.append((f, dur))
        print(f"  + {f.name} ({dur:.0f}s)")

    add(frame_title(),   8.0)
    add(frame_problem(), 10.0)
    add(frame_architecture(), 12.0)
    add(frame_incident("INC-001", data["ev1"],  1, 3), 20.0)
    add(frame_incident("INC-002", data["ev2"],  2, 3), 18.0)
    add(frame_incident("INC-003", data["ev3"],  3, 3), 16.0)
    add(frame_arena(data["arena"]),  20.0)
    add(frame_reassess(data["ev1"], data["ev1_after"], data["update"]), 20.0)
    add(frame_end(), 12.0)

    total = sum(d for _, d in frames)
    print(f"[video] total slide time: {total:.0f}s ({total/60:.1f} min)")

    out = build_video(frames)
    print()
    print(f"✅  Video saved: {out}")
    print(f"    Open:  open '{out}'")
    print(f"    Upload to YouTube/Vimeo and paste the link into submission/SUBMISSION.md")

if __name__ == "__main__":
    main()
