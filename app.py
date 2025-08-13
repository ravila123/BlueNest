# app.py — BlueNest 💙 (Phase 1: no LLM; smarter on-device summarizer)
# Layout per convo:
# - Sidebar: Active user = Ravi | Amitha | Common
# - Ravi/Amitha: Daily “notebook” (rich text), swipe-style prev/next (±7 days), calendar for others, Ask BlueNest (summarizer)
# - Common: Wish List, Vision Board (blank board: text/image/video), Travel, Ask BlueNest (summarizer across both)
# - Dark cozy UI, emoji badges for small polish
#
# NOTE: For rich text, install:  pip install "streamlit-quill>=0.1.0"

import os
import re
import json
import calendar
import datetime as dt
from typing import Optional, Dict, List, Tuple

import streamlit as st
import pandas as pd
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, Date, Text, DateTime, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Rich text editor (optional, falls back to textarea if missing)
try:
    from streamlit_quill import st_quill
except Exception:
    st_quill = None

APP_TITLE = "BlueNest 💙"
DEFAULT_USERS = ["Ravi", "Amitha"]

# ---------- Database ----------
DB_PATH = os.environ.get("BLUENEST_DB", "bluenest.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    scope = Column(String, nullable=False, default="daily")  # reserved for future (weekly/monthly/etc)
    due_date = Column(Date, nullable=True)  # used for daily
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    notes = Column(Text, default="")
    user = relationship("User")

class Wish(Base):
    __tablename__ = "wishes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    item = Column(String, nullable=False)
    link = Column(String, nullable=True)
    priority = Column(String, default="Medium")  # Low/Medium/High
    acquired = Column(Boolean, default=False)
    user = relationship("User")

class Board(Base):
    """
    Flexible blank board:
      kind: 'text' | 'image' | 'video'
      content: text content or video URL
      media_path: local path for uploaded image/video file (optional)
    """
    __tablename__ = "vision_board"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(String, default="text")
    content = Column(Text, default="")
    media_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    user = relationship("User")

class Travel(Base):
    __tablename__ = "travel_goals"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    place = Column(String, nullable=False)
    timeline = Column(String, default="2025")
    status = Column(String, default="Planned")  # Planned/Booked/Done
    notes = Column(Text, default="")
    user = relationship("User")

class DailyNote(Base):
    """Rich daily notebook (Quill delta JSON) per user per date"""
    __tablename__ = "daily_notes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    content_json = Column(Text, default="{}")  # quill delta JSON string
    updated_at = Column(DateTime, default=dt.datetime.utcnow)
    user = relationship("User")

def init_db():
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        if not s.query(User).count():
            for n in DEFAULT_USERS:
                s.add(User(name=n))
            s.commit()
init_db()

# ---------- Helpers ----------
def get_user_by_name(name: str) -> User:
    with SessionLocal() as s:
        u = s.query(User).filter(User.name == name).first()
        if not u:
            u = User(name=name)
            s.add(u); s.commit(); s.refresh(u)
        return u

def pick_emoji(text: str) -> str:
    t = text.lower()
    mapping = [
        (r"\b(run|gym|workout|yoga|lift|walk|ride|swim|steps)\b","💪"),
        (r"\b(call|phone)\b","📞"),
        (r"\b(email|mail)\b","✉️"),
        (r"\bbook|tickets|flight|hotel)\b","✈️"),
        (r"\bmeet|meeting|sync|standup|review\b","🤝"),
        (r"\bpay|bill|invoice\b","💳"),
        (r"\bshop|buy|order\b","🛒"),
        (r"\bcook|meal|lunch|dinner|breakfast\b","🍽️"),
        (r"\bread\b","📚"),
        (r"\bcode|bug|deploy|commit\b","💻"),
        (r"\bclean|laundry|dish|trash\b","🧹"),
        (r"\btravel|trip|itinerary\b","🧭"),
    ]
    for pat, emo in mapping:
        if re.search(pat, t): return emo
    return "🗒️"

def get_or_create_daily_note(user_id: int, date: dt.date) -> DailyNote:
    with SessionLocal() as s:
        note = s.query(DailyNote).filter(DailyNote.user_id==user_id, DailyNote.date==date).first()
        if not note:
            note = DailyNote(user_id=user_id, date=date, content_json=json.dumps({"ops":[{"insert":"\n"}]}))
            s.add(note); s.commit(); s.refresh(note)
        return note

def save_daily_note(note_id: int, content: dict):
    with SessionLocal() as s:
        note = s.query(DailyNote).get(note_id)
        if note:
            note.content_json = json.dumps(content or {})
            note.updated_at = dt.datetime.utcnow()
            s.commit()

def delete_row(model, row_id: int):
    with SessionLocal() as s:
        obj = s.query(model).get(row_id)
        if obj:
            s.delete(obj); s.commit()

def quill_delta_to_text(delta_json: str) -> str:
    """Flatten Quill delta to plain text for summarization/search."""
    try:
        ops = json.loads(delta_json or "{}").get("ops", [])
        return "".join(op.get("insert","") for op in ops)
    except Exception:
        return ""

# --------- Date parsing for questions (no external libs) ----------
WEEKDAYS = {name.lower(): i for i, name in enumerate(calendar.day_name)}  # monday=0..sunday=6
MONTHS = {name.lower(): i+1 for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): i+1 for i, name in enumerate(calendar.month_abbr) if name})

def parse_human_date(q: str, today: dt.date) -> Optional[dt.date]:
    """Parse simple date phrases like 'April 10', 'Apr 10 2025', 'yesterday', 'last Tuesday', 'next Fri'."""
    ql = q.lower()

    # today / yesterday / tomorrow
    if "today" in ql: return today
    if "yesterday" in ql: return today - dt.timedelta(days=1)
    if "tomorrow" in ql: return today + dt.timedelta(days=1)

    # last/next weekday (limit search within 14 days)
    m = re.search(r"\b(last|next)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", ql)
    if m:
        direction, wd = m.group(1), m.group(2)
        target = WEEKDAYS[wd]
        delta = (target - today.weekday()) % 7
        if direction == "next":
            delta = 7 if delta == 0 else delta
            return today + dt.timedelta(days=delta)
        else:  # last
            delta = 7 if delta == 0 else delta
            return today - dt.timedelta(days=delta)

    # explicit yyyy-mm-dd or mm/dd/yyyy
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", ql)
    if m:
        y, mo, d = map(int, m.groups())
        try: return dt.date(y, mo, d)
        except: pass
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", ql)
    if m:
        mo, d, y = map(int, m.groups())
        try: return dt.date(y, mo, d)
        except: pass

    # "April 10", "Apr 10th", "10 April 2025"
    # Month name first
    m = re.search(r"\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?(?:,\s*(\d{4}))?\b", q)
    if m:
        mon_name, day_str, year_str = m.groups()
        mo = MONTHS.get(mon_name.lower())
        if mo:
            day = int(day_str)
            year = int(year_str) if year_str else today.year
            try: return dt.date(year, mo, day)
            except: pass
    # Day first
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})(?:\s+(\d{4}))?\b", q)
    if m:
        day_str, mon_name, year_str = m.groups()
        mo = MONTHS.get(mon_name.lower())
        if mo:
            day = int(day_str)
            year = int(year_str) if year_str else today.year
            try: return dt.date(year, mo, day)
            except: pass

    return None

def detect_subject(q: str, default_user: str) -> Tuple[str, List[str]]:
    """Return mode: 'single' or 'both', and target names list."""
    ql = q.lower()
    if " we " in f" {ql} " or " both " in f" {ql} " or "together" in ql:
        return "both", DEFAULT_USERS
    for name in DEFAULT_USERS:
        if name.lower() in ql:
            return "single", [name]
    if "my " in ql or "me " in f"{ql} ":  # rough heuristic
        return "single", [default_user]
    return "single", [default_user]

# --------- Summarizer (no LLM) ----------
def summarize_day_for_users(date: dt.date, names: List[str]) -> str:
    """Summarize daily notes + tasks for given date and users."""
    lines = [f"### Summary for {date.strftime('%A, %B %d, %Y')}"]
    with SessionLocal() as s:
        for nm in names:
            u = s.query(User).filter(User.name==nm).first()
            if not u:
                lines.append(f"- {nm}: no profile found."); continue
            # Note
            dn = s.query(DailyNote).filter(DailyNote.user_id==u.id, DailyNote.date==date).first()
            note_text = quill_delta_to_text(dn.content_json)[:800].strip() if dn else ""
            # Tasks
            tasks = s.query(Task).filter(Task.user_id==u.id, Task.scope=="daily", Task.due_date==date)\
                                 .order_by(Task.completed.asc(), Task.created_at.desc()).all()
            lines.append(f"**{nm}**")
            if note_text:
                lines.append(f"- Notebook: {note_text}")
            else:
                lines.append("- Notebook: (empty)")
            if tasks:
                for t in tasks[:20]:
                    lines.append(f"- [{'x' if t.completed else ' '}] {t.title}")
            else:
                lines.append("- Tasks: (none)")
    return "\n".join(lines)

def ask_bluenest_summarizer(question: str, default_user: str) -> str:
    """Answers date-based questions and simple summaries from stored data (no external LLM)."""
    today = dt.date.today()
    mode, targets = detect_subject(question, default_user)
    d = parse_human_date(question, today)

    if d:
        # Single day summary
        if mode == "both":
            return summarize_day_for_users(d, DEFAULT_USERS)
        else:
            return summarize_day_for_users(d, targets)
    # If no date matched, try lightweight intents
    ql = question.lower()
    with SessionLocal() as s:
        if "today" in ql or "now" in ql:
            d = today
            if mode == "both":
                return summarize_day_for_users(d, DEFAULT_USERS)
            else:
                return summarize_day_for_users(d, targets)
        if "yesterday" in ql:
            d = today - dt.timedelta(days=1)
            if mode == "both":
                return summarize_day_for_users(d, DEFAULT_USERS)
            else:
                return summarize_day_for_users(d, targets)

    # Fallback: explain how to ask
    return ("I can summarize a specific day for you. Try:\n"
            "- “what did I do on April 10?”\n"
            "- “what did we do on April 11th?”\n"
            "- “what did Amitha do yesterday?”\n"
            "- “what did Ravi do last Tuesday?”")

# ---------- UI ----------
st.set_page_config(page_title="BlueNest", page_icon="💙", layout="wide")

# Cozy dark background
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
  background: radial-gradient(1200px 600px at 10% 10%, rgba(56,189,248,.08), transparent 60%),
              radial-gradient(1200px 600px at 90% 20%, rgba(56,189,248,.06), transparent 60%),
              linear-gradient(180deg, #0b1220 0%, #0b1220 100%);
}
.block-container { padding-top: 1rem; padding-bottom: 3rem; }
h1, h2, h3 { letter-spacing: .3px; }
.bubble {
  background: rgba(17,24,39,.65);
  border: 1px solid rgba(56,189,248,.25);
  border-radius: 14px; padding: 12px 14px; margin-bottom: 12px;
  box-shadow: 0 8px 22px rgba(2,132,199,.08);
}
.tag { font-size:.78rem; padding:.12rem .5rem; border-radius:999px; border:1px solid rgba(56,189,248,.35); }
.title-row { display:flex; align-items:center; gap:.6rem; }
.title-heart { font-size:1.6rem; line-height:1; }
.sidebar-section-title { font-size:.9rem; opacity:.8; margin-top:.5rem; }
</style>
""", unsafe_allow_html=True)

# Sidebar: Active User + Section nav
with st.sidebar:
    st.markdown("### <div class='title-row'><span class='title-heart'>💙</span><span>BlueNest</span></div>", unsafe_allow_html=True)
    st.caption("A cozy, shared planner for Ravi & Amitha.")

    # ensure users exist
    with SessionLocal() as s:
        user_names = [u.name for u in s.query(User).order_by(User.name).all()]
    for required in DEFAULT_USERS:
        if required not in user_names:
            get_user_by_name(required)
    with SessionLocal() as s:
        user_names = [u.name for u in s.query(User).order_by(User.name).all()]

    persona = st.radio("Active user", options=["Ravi","Amitha","Common"], index=0 if "Ravi" in user_names else 2, horizontal=True)
    if persona != "Common":
        current_user = get_user_by_name(persona)
        st.markdown("<div class='sidebar-section-title'>Personal</div>", unsafe_allow_html=True)
        section = st.radio("Section", ["Dashboard","Daily","Ask BlueNest"], index=1)
    else:
        current_user = None
        st.markdown("<div class='sidebar-section-title'>Common</div>", unsafe_allow_html=True)
        section = st.radio("Section", ["Dashboard","Wish List","Vision Board","Travel","Ask BlueNest"], index=1)

today = dt.date.today()
st.markdown(f"## {APP_TITLE}")
st.caption(today.strftime('%A, %B %d, %Y'))

# Dashboard (simple summary)
def render_dashboard(user_name: Optional[str]):
    with SessionLocal() as s:
        if user_name:
            u = s.query(User).filter(User.name==user_name).first()
            if u:
                # Daily tasks quick stats
                total_today = s.query(Task).filter(Task.user_id==u.id, Task.scope=="daily", Task.due_date==today).count()
                done_today = s.query(Task).filter(Task.user_id==u.id, Task.scope=="daily", Task.due_date==today, Task.completed==True).count()
                pct = int((done_today/total_today)*100) if total_today else 0
                st.markdown(
                    f'<div class="bubble"><b>Hi, {user_name}!</b> '
                    f'You’ve completed <b>{done_today}</b> of <b>{total_today}</b> today — <b>{pct}%</b>.</div>',
                    unsafe_allow_html=True
                )
        else:
            # Common dashboard: quick wish/travel counts
            wish_open = s.query(Wish).filter(Wish.acquired==False).count()
            trip_planned = s.query(Travel).filter(Travel.status!="Done").count()
            st.markdown(
                f'<div class="bubble">Shared snapshot — open wishes: <b>{wish_open}</b>, upcoming trips: <b>{trip_planned}</b>.</div>',
                unsafe_allow_html=True
            )

# Daily notebook page (rich text, swipe prev/next ±7 days, calendar for others)
def render_daily(user: User):
    st.markdown("### Daily Notebook")

    # state date
    key = f"daily_date_{user.id}"
    if key not in st.session_state:
        st.session_state[key] = today

    # toolbar: prev/next limited ±7 days from today, plus calendar
    d: dt.date = st.session_state[key]
    colA, colB, colC, colD = st.columns([0.1,0.3,0.3,0.3])
    with colA:
        st.write("")  # spacing
        can_prev = (today - d).days <= 0 and (d - (today - dt.timedelta(days=7))).days > 0
        if st.button("←", disabled=not can_prev):
            st.session_state[key] = d - dt.timedelta(days=1)
            st.rerun()
    with colB:
        st.markdown(f"**{d.strftime('%A, %B %d, %Y')}**")
    with colC:
        pick = st.date_input("Go to date", value=d, label_visibility="collapsed")
        if pick != d:
            st.session_state[key] = pick
            st.rerun()
    with colD:
        can_next = (d - today).days < 0 and (today - d).days <= 7
        if st.button("→", disabled=not can_next):
            st.session_state[key] = d + dt.timedelta(days=1)
            st.rerun()

    note = get_or_create_daily_note(user.id, st.session_state[key])
    st.write("")  # spacer

    st.markdown("**Notebook**")
    if st_quill is None:
        st.warning("Install the rich text editor: `pip install streamlit-quill`")
        raw = st.text_area("Notes", value=quill_delta_to_text(note.content_json), placeholder="Start typing… (bold, bullets etc. available when streamlit-quill is installed)")
        if st.button("Save"):
            save_daily_note(note.id, {"ops":[{"insert": raw + "\n"}]})
            st.success("Saved."); st.rerun()
    else:
        try:
            content_dict = json.loads(note.content_json or "{}")
        except Exception:
            content_dict = {"ops":[{"insert":"\n"}]}
        result = st_quill(value=content_dict, placeholder="Type here • • •", key=f"quill_{note.id}", html=False, toolbar=True)
        if st.button("Save"):
            save_daily_note(note.id, result or {"ops":[{"insert":"\n"}]})
            st.success("Saved."); st.rerun()

    st.markdown("---")
    st.markdown("**Optional quick to-dos for this day**")
    t_title = st.text_input("Add a to-do", key=f"todo_title_{user.id}", placeholder="Describe the task…")
    if st.button("Add to-do", key=f"todo_add_{user.id}"):
        if t_title.strip():
            with SessionLocal() as s:
                s.add(Task(user_id=user.id, title=f"{pick_emoji(t_title)} {t_title.strip()}", scope="daily", due_date=st.session_state[key]))
                s.commit()
            st.success("Task added."); st.rerun()

    with SessionLocal() as s:
        tasks = s.query(Task).filter(Task.user_id==user.id, Task.scope=="daily", Task.due_date==st.session_state[key])\
                             .order_by(Task.completed.asc(), Task.created_at.desc()).all()
    if tasks:
        for t in tasks:
            c1,c2,c3 = st.columns([0.08, 0.74, 0.18])
            with c1:
                checked = st.checkbox("", value=t.completed, key=f"chk_{t.id}")
                if checked != t.completed:
                    with SessionLocal() as s:
                        tt = s.query(Task).get(t.id); tt.completed = checked; s.commit()
                    st.rerun()
            with c2:
                st.markdown(f"**{t.title}**")
                if t.notes:
                    st.caption(t.notes)
            with c3:
                if st.button("🗑️", key=f"del_{t.id}"):
                    delete_row(Task, t.id); st.rerun()
    else:
        st.info("No to-dos yet — add one above ✨")

# Ask BlueNest (Summarizer only; no LLM)
def render_ask(user_name_opt: Optional[str]):
    st.markdown("### 🤖 Ask BlueNest (Summarizer)")
    q = st.text_input("Ask things like “what did I do on April 10?”, “what did we do on April 11th?”, “what did Amitha do last Tuesday?”")
    if q:
        default_user = user_name_opt or "Ravi"
        ans = ask_bluenest_summarizer(q, default_user)
        st.markdown(ans.replace("\n", "  \n"))

# Common: Wish List
def render_wish_list():
    st.markdown("### Wish List (Common)")
    colA, colB, colC, colD = st.columns([0.38, 0.32, 0.18, 0.12])
    with colA: w_item = st.text_input("What do you want?", key="wish_item", placeholder="Noise-canceling headphones")
    with colB: w_link = st.text_input("Link (optional)", key="wish_link", placeholder="https://…")
    with colC: w_pri = st.selectbox("Priority", ["Low","Medium","High"], index=1, key="wish_pri")
    with colD:
        st.write("")
        if st.button("Add ➕", use_container_width=True, key="wish_add"):
            if w_item.strip():
                with SessionLocal() as s:
                    # store under Ravi by convention; Common view shows all
                    s.add(Wish(user_id=get_user_by_name("Ravi").id, item=f"🎁 {w_item.strip()}", link=w_link.strip(), priority=w_pri)); s.commit()
                st.success("Added to wish list."); st.rerun()
    with SessionLocal() as s:
        wishes = s.query(Wish).order_by(Wish.acquired.asc(), Wish.priority.desc()).all()
    if wishes:
        for w in wishes:
            cols = st.columns([0.06, 0.58, 0.24, 0.12])
            with cols[0]:
                got = st.checkbox("", value=w.acquired, key=f"wish_chk_{w.id}")
                if got != w.acquired:
                    with SessionLocal() as s:
                        ww = s.query(Wish).get(w.id); ww.acquired = got; s.commit()
                    st.rerun()
            with cols[1]:
                txt = f"**{w.item}**"
                if w.link: txt += f" &nbsp; <a href='{w.link}' target='_blank'>🔗 Link</a>"
                st.markdown(txt, unsafe_allow_html=True)
            with cols[2]: st.markdown(f"<span class='tag'>Priority: {w.priority}</span>", unsafe_allow_html=True)
            with cols[3]:
                if st.button("🗑️", key=f"wish_del_{w.id}"): delete_row(Wish, w.id); st.rerun()
    else: st.info("Add your first wish ✨")

# Common: Vision Board (blank board — text / image / video blocks)
def render_vision_board():
    st.markdown("### Vision Board (Common)")
    st.caption("Drop text, images, or videos. No forced captions/tags — just a cozy board.")

    kind = st.radio("Add a block", ["Text","Image","Video"], horizontal=True)
    if kind == "Text":
        txt = st.text_area("Write something", placeholder="Type your thought…")
        if st.button("Add ➕", key="vb_add_text"):
            if txt.strip():
                with SessionLocal() as s:
                    s.add(Board(user_id=get_user_by_name("Ravi").id, kind="text", content=txt.strip())); s.commit()
                st.success("Added."); st.rerun()
    elif kind == "Image":
        img = st.file_uploader("Upload an image", type=["png","jpg","jpeg","webp"], key="vb_img")
        if st.button("Add ➕", key="vb_add_img"):
            if img:
                upload_dir = "uploads"; os.makedirs(upload_dir, exist_ok=True)
                path = os.path.join(upload_dir, f"{dt.datetime.utcnow().timestamp()}_{img.name}")
                with open(path,"wb") as f: f.write(img.read())
                with SessionLocal() as s:
                    s.add(Board(user_id=get_user_by_name("Ravi").id, kind="image", content="", media_path=path)); s.commit()
                st.success("Added."); st.rerun()
    else:  # Video
        url = st.text_input("YouTube/Video URL (or upload a video file below)")
        vid = st.file_uploader("Upload a video file (optional)", type=["mp4","mov","m4v","webm"], key="vb_vid")
        if st.button("Add ➕", key="vb_add_vid"):
            media_path = None
            if vid:
                upload_dir = "uploads"; os.makedirs(upload_dir, exist_ok=True)
                media_path = os.path.join(upload_dir, f"{dt.datetime.utcnow().timestamp()}_{vid.name}")
                with open(media_path,"wb") as f: f.write(vid.read())
            with SessionLocal() as s:
                s.add(Board(user_id=get_user_by_name("Ravi").id, kind="video", content=(url or ""), media_path=media_path)); s.commit()
            st.success("Added."); st.rerun()

    # grid
    with SessionLocal() as s:
        cards = s.query(Board).order_by(Board.created_at.desc()).all()
    if cards:
        grid_cols = st.columns(3)
        for i, c in enumerate(cards):
            with grid_cols[i % 3]:
                if c.kind == "text":
                    st.markdown(f'<div class="bubble">{c.content}</div>', unsafe_allow_html=True)
                elif c.kind == "image":
                    if c.media_path and os.path.exists(c.media_path):
                        st.image(c.media_path, use_column_width=True)
                else:  # video
                    if c.content and c.content.startswith("http"):
                        st.video(c.content)
                    elif c.media_path and os.path.exists(c.media_path):
                        st.video(c.media_path)
                if st.button("🗑️ Remove", key=f"vb_del_{c.id}"):
                    delete_row(Board, c.id)
                    if c.media_path and os.path.exists(c.media_path):
                        try: os.remove(c.media_path)
                        except: pass
                    st.rerun()
    else:
        st.info("Your board is empty — add a block above.")

# Common: Travel
def render_travel():
    st.markdown("### Travel (Common)")
    c1, c2, c3 = st.columns([0.4,0.3,0.3])
    with c1: place = st.text_input("Destination", key="t_place", placeholder="Kyoto")
    with c2: timeline = st.text_input("Target Timeline", key="t_time", placeholder="Oct 2025")
    with c3: status = st.selectbox("Status", ["Planned","Booked","Done"], index=0, key="t_status")
    notes = st.text_area("Notes", key="t_notes", placeholder="Accommodation ideas, must-do spots…")
    if st.button("Add Trip ➕", key="t_add"):
        with SessionLocal() as s:
            s.add(Travel(user_id=get_user_by_name("Ravi").id, place=f"🧭 {place or 'Somewhere'}", timeline=timeline or "2025", status=status, notes=notes)); s.commit()
        st.success("Trip added."); st.rerun()

    with SessionLocal() as s:
        trips = s.query(Travel).order_by(Travel.status.asc()).all()
    if trips:
        df = pd.DataFrame([{"Destination": tr.place, "Timeline": tr.timeline, "Status": tr.status, "Notes": tr.notes, "ID": tr.id} for tr in trips])
        st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)
        del_id = st.selectbox("Remove a trip (optional)", options=["—"] + [str(tr.id) for tr in trips], key="t_del")
        if del_id != "—": delete_row(Travel, int(del_id)); st.rerun()
    else: st.info("Add your first travel plan ✈️")

# ----- Router -----
if persona != "Common":
    # Ravi or Amitha
    if section == "Dashboard":
        render_dashboard(persona)
    elif section == "Daily":
        render_daily(current_user)
    elif section == "Ask BlueNest":
        render_ask(persona)
else:
    # Common
    if section == "Dashboard":
        render_dashboard(None)
    elif section == "Wish List":
        render_wish_list()
    elif section == "Vision Board":
        render_vision_board()
    elif section == "Travel":
        render_travel()
    elif section == "Ask BlueNest":
        render_ask(None)