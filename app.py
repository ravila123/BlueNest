# app.py — BlueNest 💙 (Ultra-minimal To-Do, Notebook on right tab, tiny Ask Blue chat)
# Requirements:
#   streamlit>=1.36.0, sqlalchemy>=2.0.0, pandas>=2.0.0
# Optional (for rich Notebook): streamlit-quill==0.0.3  (falls back to textarea if unavailable)

import os
import re
import json
import calendar
import datetime as dt
from typing import Optional, List, Tuple

import streamlit as st
import pandas as pd
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, Date, Text, DateTime, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Optional rich editor for the Notebook tab
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
    scope = Column(String, nullable=False, default="daily")
    due_date = Column(Date, nullable=True)  # used for daily
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    notes = Column(Text, default="")
    user = relationship("User")

class DailyNote(Base):
    """Daily notebook (Quill delta JSON) per user per date"""
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

def delete_row(model, row_id: int):
    with SessionLocal() as s:
        obj = s.query(model).get(row_id)
        if obj:
            s.delete(obj); s.commit()

def quill_delta_to_text(delta_json: str) -> str:
    try:
        ops = json.loads(delta_json or "{}").get("ops", [])
        return "".join(op.get("insert","") for op in ops)
    except Exception:
        return ""

# --------- Summarizer (no LLM) ----------
WEEKDAYS = {name.lower(): i for i, name in enumerate(calendar.day_name)}  # monday=0..sunday=6
MONTHS = {name.lower(): i+1 for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): i+1 for i, name in enumerate(calendar.month_abbr) if name})

def parse_human_date(q: str, today: dt.date) -> Optional[dt.date]:
    ql = q.lower()

    if "today" in ql: return today
    if "yesterday" in ql: return today - dt.timedelta(days=1)
    if "tomorrow" in ql: return today + dt.timedelta(days=1)

    m = re.search(r"\b(last|next)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", ql)
    if m:
        direction, wd = m.group(1), m.group(2)
        target = WEEKDAYS[wd]
        delta = (target - today.weekday()) % 7
        if direction == "next":
            delta = 7 if delta == 0 else delta
            return today + dt.timedelta(days=delta)
        else:
            delta = 7 if delta == 0 else delta
            return today - dt.timedelta(days=delta)

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

    m = re.search(r"\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?(?:,\s*(\d{4}))?\b", q)
    if m:
        mon_name, day_str, year_str = m.groups()
        mo = MONTHS.get(mon_name.lower())
        if mo:
            day = int(day_str)
            year = int(year_str) if year_str else today.year
            try: return dt.date(year, mo, day)
            except: pass

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
    ql = q.lower()
    for name in DEFAULT_USERS:
        if name.lower() in ql:
            return "single", [name]
    if " my " in f" {ql} " or ql.startswith("what did i"):
        return "single", [default_user]
    # default: active user
    return "single", [default_user]

def summarize_day_for_users(date: dt.date, names: List[str]) -> str:
    lines = [f"### {date.strftime('%A, %B %d, %Y')}"]
    with SessionLocal() as s:
        for nm in names:
            u = s.query(User).filter(User.name==nm).first()
            if not u:
                lines.append(f"- {nm}: no profile found."); continue
            dn = s.query(DailyNote).filter(DailyNote.user_id==u.id, DailyNote.date==date).first()
            note_text = quill_delta_to_text(dn.content_json)[:800].strip() if dn else ""
            tasks = s.query(Task).filter(Task.user_id==u.id, Task.scope=="daily", Task.due_date==date)\
                                 .order_by(Task.completed.asc(), Task.created_at.desc()).all()
            lines.append(f"**{nm}**")
            lines.append(f"- 📝 {note_text if note_text else '(no note)'}")
            if tasks:
                for t in tasks[:20]:
                    lines.append(f"- {'✅' if t.completed else '•'} {t.title}")
            else:
                lines.append("- (no tasks)")
            lines.append("")  # spacer
    return "\n".join(lines).strip()

def ask_bluenest_summarizer(question: str, default_user: str) -> str:
    today = dt.date.today()
    mode, targets = detect_subject(question, default_user)
    d = parse_human_date(question, today)
    if d:
        return summarize_day_for_users(d, targets)
    # gentle help
    return ("Try things like:\n"
            "- “what did I do on April 10?”\n"
            "- “what did Amitha do yesterday?”\n"
            "- “what did Ravi do last Tuesday?”\n"
            "- “what did I do 2025-04-07?”")

# ---------- UI ----------
st.set_page_config(page_title="BlueNest", page_icon="💙", layout="wide")

# Clean, understated dark background + minimal elements (no big boxes)
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
  background: radial-gradient(1100px 520px at 10% 10%, rgba(56,189,248,.07), transparent 55%),
              radial-gradient(1100px 520px at 92% 14%, rgba(56,189,248,.05), transparent 55%),
              linear-gradient(180deg, #0b1220 0%, #0b1220 100%);
}
.block-container { padding-top: 0.8rem; padding-bottom: 1.6rem; }
h1, h2, h3 { letter-spacing: .2px; }
.small { opacity:.7; font-size:.9rem; }

.todo-input input {
  background: rgba(255,255,255,0.06) !important;
  border: 1px solid rgba(56,189,248,.22) !important;
  border-radius: 12px !important;
  height: 44px; font-size: 1rem;
}
.todo-item {
  display:flex; align-items:center; gap:.6rem;
  padding:.5rem .6rem; border-radius: 12px;
  border:1px solid rgba(56,189,248,.14);
  background: rgba(17,24,39,.35);
  margin-bottom:.35rem;
}
.todo-date { font-size:.95rem; opacity:.85; letter-spacing:.2px; }

.right-sticky { position: sticky; top: 6px; z-index: 100; }
.right-row { display:flex; justify-content:flex-end; align-items:center; gap:.4rem; }
.right-row .dogbtn button {
  border-radius: 999px; width: 40px; height: 40px; font-size: 20px;
  border: 1px solid rgba(56,189,248,.35); background: rgba(17,24,39,.55);
}
.chatbox {
  background: rgba(17,24,39,.92);
  border:1px solid rgba(56,189,248,.30);
  border-radius: 12px; padding: 10px; width: 300px;
  box-shadow: 0 10px 28px rgba(2,132,199,.22);
  margin-left: auto;
}
.quiet-divider { height: 8px; }
</style>
""", unsafe_allow_html=True)

# Sidebar: Active user only (NO "Common" mode)
with st.sidebar:
    st.markdown("### BlueNest 💙")
    st.caption("Ultra-minimal daily to-dos")

    # ensure Ravi & Amitha exist
    with SessionLocal() as s:
        user_names = [u.name for u in s.query(User).order_by(User.name).all()]
    for required in DEFAULT_USERS:
        if required not in user_names:
            get_user_by_name(required)
    with SessionLocal() as s:
        user_names = [u.name for u in s.query(User).order_by(User.name).all()]

    persona = st.radio("Active user", options=DEFAULT_USERS,
                       index=0 if "Ravi" in user_names else 1, horizontal=True)

today = dt.date.today()
st.markdown(f"## {APP_TITLE}")
st.caption(today.strftime('%A, %B %d, %Y'))

# ---------- Layout: two columns (left = To-Do only, right = dog + Notebook tab) ----------
left, right = st.columns([0.66, 0.34], gap="large")

# ========== RIGHT PANEL ==========
with right:
    st.markdown("<div class='right-sticky'>", unsafe_allow_html=True)
    row_l, row_r = st.columns([0.55, 0.45])
    with row_r:
        st.markdown("<div class='right-row'>", unsafe_allow_html=True)
        if "show_blue" not in st.session_state: st.session_state.show_blue = False
        with st.container():
            if st.button("🐶", key="blueboy_toggle", help="Ask Blue", use_container_width=False):
                st.session_state.show_blue = not st.session_state.show_blue
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.show_blue:
        st.markdown("<div class='chatbox'>", unsafe_allow_html=True)
        st.markdown("**Hey! It's Blue boy!!**  \n*what do you want to know from me?*")
        default_user = persona
        q = st.text_input("Ask about a date", key="blue_q", label_visibility="collapsed",
                          placeholder="e.g., what did I do on April 10?")
        if q:
            ans = ask_bluenest_summarizer(q, default_user)
            st.markdown(ans.replace("\n","  \n"))
        if st.button("Close", key="blue_close", use_container_width=True):
            st.session_state.show_blue = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # Notebook tab ONLY here (not in the To-Do window)
    tabs = st.tabs(["Notebook"])
    with tabs[0]:
        current_user = get_user_by_name(persona)
        date_key = f"todo_date_{current_user.id}"
        if date_key not in st.session_state:
            st.session_state[date_key] = today
        note_date = st.session_state[date_key]

        # ensure note exists
        with SessionLocal() as s:
            dn = s.query(DailyNote).filter(DailyNote.user_id==current_user.id,
                                           DailyNote.date==note_date).first()
            if not dn:
                dn = DailyNote(user_id=current_user.id, date=note_date,
                               content_json=json.dumps({"ops":[{"insert":"\n"}]}))
                s.add(dn); s.commit(); s.refresh(dn)

        st.caption(f"{current_user.name} — {note_date.strftime('%a, %b %d, %Y')}")
        if st_quill is None:
            raw = st.text_area("",
                               value=quill_delta_to_text(dn.content_json),
                               placeholder="Write your note…",
                               label_visibility="collapsed",
                               height=200)
            # No big success boxes; just a quiet save
            if st.button("Save", key=f"save_note_{current_user.id}"):
                with SessionLocal() as s:
                    nn = s.query(DailyNote).get(dn.id)
                    nn.content_json = json.dumps({"ops":[{"insert": raw + "\n"}]})
                    nn.updated_at = dt.datetime.utcnow()
                    s.commit()
                st.caption("Saved")  # subtle
        else:
            try:
                content_dict = json.loads(dn.content_json or "{}")
            except Exception:
                content_dict = {"ops":[{"insert":"\n"}]}
            result = st_quill(value=content_dict, placeholder="Write your note…",
                              key=f"quill_{dn.id}", html=False, toolbar=True)
            if st.button("Save", key=f"save_quill_{current_user.id}"):
                with SessionLocal() as s:
                    nn = s.query(DailyNote).get(dn.id)
                    nn.content_json = json.dumps(result or {"ops":[{"insert":"\n"}]})
                    nn.updated_at = dt.datetime.utcnow()
                    s.commit()
                st.caption("Saved")  # subtle

# ========== LEFT (MAIN) — MINIMAL TO-DO ONLY ==========
with left:
    user = get_user_by_name(persona)

    # date state + controls
    key_date = f"todo_date_{user.id}"
    if key_date not in st.session_state:
        st.session_state[key_date] = today

    d: dt.date = st.session_state[key_date]
    c_top = st.columns([0.12, 0.48, 0.40])
    with c_top[0]:
        can_prev = (today - d).days <= 0 and (d - (today - dt.timedelta(days=7))).days > 0
        if st.button("←", disabled=not can_prev, key=f"prev_{user.id}"):
            st.session_state[key_date] = d - dt.timedelta(days=1); st.rerun()
    with c_top[1]:
        st.markdown(f"<div class='todo-date'><b>{d.strftime('%A, %B %d')}</b></div>", unsafe_allow_html=True)
    with c_top[2]:
        pick = st.date_input("Pick date", value=d, label_visibility="collapsed", key=f"pick_{user.id}")
        if pick != d:
            st.session_state[key_date] = pick; st.rerun()

    # To-Do input (Enter to add) — NO emoji auto-tagging
    st.markdown("<div class='todo-input'>", unsafe_allow_html=True)
    key_input = f"new_task_{user.id}"
    def _add_on_enter():
        title = (st.session_state.get(key_input) or "").strip()
        if title:
            with SessionLocal() as s:
                s.add(Task(user_id=user.id, title=title, scope="daily", due_date=st.session_state[key_date]))
                s.commit()
            st.session_state[key_input] = ""
            st.rerun()
    st.text_input("Add a task", key=key_input, placeholder="Type and press Enter…",
                  on_change=_add_on_enter, label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

    # Tasks list (clean, minimal)
    with SessionLocal() as s:
        tasks = s.query(Task).filter(Task.user_id==user.id, Task.scope=="daily",
                                     Task.due_date==st.session_state[key_date])\
                             .order_by(Task.completed.asc(), Task.created_at.desc()).all()
    if not tasks:
        st.caption("No tasks yet — add one above")
    else:
        for t in tasks:
            st.markdown("<div class='todo-item'>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([0.08, 0.76, 0.16])
            with col1:
                checked = st.checkbox("", value=t.completed, key=f"chk_{t.id}")
                if checked != t.completed:
                    with SessionLocal() as s:
                        tt = s.query(Task).get(t.id); tt.completed = checked; s.commit()
                    st.rerun()
            with col2:
                st.markdown(f"{t.title}")
            with col3:
                if st.button("🗑️", key=f"del_{t.id}"):
                    delete_row(Task, t.id); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)