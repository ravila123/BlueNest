# app.py — BlueNest 💙 (Minimal To-Do focus; Notebook on right tab; tiny Ask Blue chat in top-right panel)
# Requirements:
#   streamlit>=1.36.0, sqlalchemy>=2.0.0, pandas>=2.0.0
# Optional (for rich Notebook): streamlit-quill==0.0.3  (falls back to textarea if missing)

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
    """Blank board blocks: text / image / video"""
    __tablename__ = "vision_board"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(String, default="text")   # 'text' | 'image' | 'video'
    content = Column(Text, default="")      # text or video URL
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

def pick_emoji(text: str) -> str:
    t = text.lower()
    mapping = [
        (r"\b(run|gym|workout|yoga|lift|walk|ride|swim|steps)\b","💪"),
        (r"\b(call|phone)\b","📞"),
        (r"\b(email|mail)\b","✉️"),
        (r"\bbook|tickets|flight|hotel\b","✈️"),
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
    return "•"

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
    if " we " in f" {ql} " or " both " in f" {ql} " or "together" in ql:
        return "both", DEFAULT_USERS
    for name in DEFAULT_USERS:
        if name.lower() in ql:
            return "single", [name]
    if " my " in f" {ql} " or ql.startswith("what did i"):
        return "single", [default_user]
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
        if mode == "both":
            return summarize_day_for_users(d, DEFAULT_USERS)
        else:
            return summarize_day_for_users(d, targets)
    # gentle help
    return ("Try things like:\n"
            "- “what did I do on April 10?”\n"
            "- “what did we do yesterday?”\n"
            "- “what did Amitha do last Tuesday?”\n"
            "- “what did Ravi do 2025-04-07?”")

# ---------- UI ----------
st.set_page_config(page_title="BlueNest", page_icon="💙", layout="wide")

# Aesthetic dark background + right panel sticky header (keeps the dog button top-right)
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
  background: radial-gradient(1200px 600px at 10% 10%, rgba(56,189,248,.08), transparent 60%),
              radial-gradient(1200px 600px at 90% 20%, rgba(56,189,248,.06), transparent 60%),
              linear-gradient(180deg, #0b1220 0%, #0b1220 100%);
}
.block-container { padding-top: 1rem; padding-bottom: 2rem; }
h1, h2, h3 { letter-spacing: .3px; }
.minibox {
  background: rgba(17,24,39,.65);
  border: 1px solid rgba(56,189,248,.25);
  border-radius: 14px; padding: 12px 14px; margin-bottom: 12px;
  box-shadow: 0 8px 22px rgba(2,132,199,.08);
}
.todo-input input {
  background: rgba(255,255,255,0.06) !important;
  border: 1px solid rgba(56,189,248,.25) !important;
  border-radius: 12px !important;
  height: 44px; font-size: 1rem;
}
.todo-item {
  display:flex; align-items:center; gap:.6rem;
  padding:.5rem .6rem; border-radius: 10px;
  border:1px solid rgba(56,189,248,.15);
  background: rgba(17,24,39,.45);
  margin-bottom:.4rem;
}
.todo-date { font-size:.95rem; opacity:.85; letter-spacing:.2px; }

.right-sticky {
  position: sticky; top: 8px;
  background: transparent;
  padding-top: 2px; padding-bottom: 6px;
  z-index: 100;
}
.right-row { display:flex; justify-content:flex-end; gap:.4rem; align-items:center; }
.right-row .dogbtn button {
  border-radius: 999px; width: 42px; height: 42px; font-size: 22px;
  border: 1px solid rgba(56,189,248,.35);
}
.chatbox {
  background: rgba(17,24,39,.90);
  border:1px solid rgba(56,189,248,.35);
  border-radius: 14px; padding: 10px; width: 320px;
  box-shadow: 0 12px 32px rgba(2,132,199,.25);
  margin-left: auto;
}
</style>
""", unsafe_allow_html=True)

# Sidebar: Active user / Common
with st.sidebar:
    st.markdown("### BlueNest 💙")
    st.caption("Minimal daily to-dos for Ravi & Amitha.")

    # ensure users exist
    with SessionLocal() as s:
        user_names = [u.name for u in s.query(User).order_by(User.name).all()]
    for required in DEFAULT_USERS:
        if required not in user_names:
            get_user_by_name(required)
    with SessionLocal() as s:
        user_names = [u.name for u in s.query(User).order_by(User.name).all()]

    persona = st.radio("Active user", options=["Ravi","Amitha","Common"],
                       index=0 if "Ravi" in user_names else 2, horizontal=True)

    if persona == "Common":
        section = st.radio("Section", ["Wish List","Vision Board","Travel"], index=0)
    else:
        section = "To-Do"

today = dt.date.today()
st.markdown(f"## {APP_TITLE}")
st.caption(today.strftime('%A, %B %d, %Y'))

# ---------- Layout: two columns (left main todo, right panel with dog + tabs) ----------
left, right = st.columns([0.64, 0.36], gap="large")

# ========== RIGHT PANEL ==========
with right:
    # Sticky top row with tiny dog button (top-right of the panel)
    st.markdown("<div class='right-sticky'>", unsafe_allow_html=True)
    row_l, row_r = st.columns([0.6, 0.4])
    with row_r:
        st.markdown("<div class='right-row'>", unsafe_allow_html=True)
        if "show_blue" not in st.session_state: st.session_state.show_blue = False
        with st.container():  # dog button
            if st.button("🐶", key="blueboy_toggle", help="Ask Blue", use_container_width=False):
                st.session_state.show_blue = not st.session_state.show_blue
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Small chat square (does not take over the screen)
    if st.session_state.show_blue:
        st.markdown("<div class='chatbox'>", unsafe_allow_html=True)
        st.markdown("**Hey! It's Blue boy!!**  \n*what do you want to know from me?*")
        default_user = "Ravi" if persona not in DEFAULT_USERS else persona
        q = st.text_input("Ask about a date", key="blue_q", label_visibility="collapsed",
                          placeholder="e.g., what did we do on April 11?")
        if q:
            ans = ask_bluenest_summarizer(q, default_user)
            st.markdown(ans.replace("\n","  \n"))
        if st.button("Close", key="blue_close", use_container_width=True):
            st.session_state.show_blue = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # Right panel tabs — Notebook is here (not in the main area)
    tabs = st.tabs(["Notebook"])
    with tabs[0]:
        # tie the notebook date to whatever the left panel is viewing
        current_user = None if persona == "Common" else get_user_by_name(persona)
        if persona == "Common":
            st.info("Pick **Ravi** or **Amitha** on the left to edit that person's Notebook.")
        else:
            # share the same date key as To-Do (so notebook & tasks align)
            date_key = f"todo_date_{current_user.id}"
            if date_key not in st.session_state:
                st.session_state[date_key] = today
            note = None
            with SessionLocal() as s:
                # ensure a note exists for that date
                dn = s.query(DailyNote).filter(DailyNote.user_id==current_user.id,
                                               DailyNote.date==st.session_state[date_key]).first()
                if not dn:
                    dn = DailyNote(user_id=current_user.id, date=st.session_state[date_key],
                                   content_json=json.dumps({"ops":[{"insert":"\n"}]}))
                    s.add(dn); s.commit(); s.refresh(dn)
                note = dn

            st.caption(f"Notebook for {current_user.name} — {st.session_state[date_key].strftime('%a, %b %d, %Y')}")
            if st_quill is None:
                raw = st.text_area("Notes", value=quill_delta_to_text(note.content_json),
                                   placeholder="Quick thoughts… (install streamlit-quill for rich editing)")
                if st.button("Save note", key=f"save_note_{current_user.id}"):
                    with SessionLocal() as s:
                        nn = s.query(DailyNote).get(note.id)
                        nn.content_json = json.dumps({"ops":[{"insert": raw + "\n"}]})
                        nn.updated_at = dt.datetime.utcnow()
                        s.commit()
                    st.success("Saved."); st.rerun()
            else:
                try:
                    content_dict = json.loads(note.content_json or "{}")
                except Exception:
                    content_dict = {"ops":[{"insert":"\n"}]}
                result = st_quill(value=content_dict, placeholder="Write freely…",
                                  key=f"quill_{note.id}", html=False, toolbar=True)
                if st.button("Save note", key=f"save_quill_{current_user.id}"):
                    with SessionLocal() as s:
                        nn = s.query(DailyNote).get(note.id)
                        nn.content_json = json.dumps(result or {"ops":[{"insert":"\n"}]})
                        nn.updated_at = dt.datetime.utcnow()
                        s.commit()
                    st.success("Saved."); st.rerun()

# ========== LEFT (MAIN) — MINIMAL TO-DO ==========
with left:
    if persona == "Common":
        st.subheader("Common")
        sec = st.radio("Choose", ["Wish List","Vision Board","Travel"], horizontal=True)
        if sec == "Wish List":
            # quick shared wish list
            colA, colB, colC, colD = st.columns([0.38, 0.32, 0.18, 0.12])
            with colA: w_item = st.text_input("What do you want?", key="wish_item", placeholder="Noise-canceling headphones")
            with colB: w_link = st.text_input("Link (optional)", key="wish_link", placeholder="https://…")
            with colC: w_pri = st.selectbox("Priority", ["Low","Medium","High"], index=1, key="wish_pri")
            with colD:
                st.write("")
                if st.button("Add ➕", use_container_width=True, key="wish_add"):
                    if w_item.strip():
                        with SessionLocal() as s:
                            s.add(Wish(user_id=get_user_by_name("Ravi").id,
                                       item=f"🎁 {w_item.strip()}", link=w_link.strip(), priority=w_pri)); s.commit()
                        st.success("Added."); st.rerun()
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
                    with cols[2]: st.markdown(f"<div class='minibox'>Priority: {w.priority}</div>", unsafe_allow_html=True)
                    with cols[3]:
                        if st.button("🗑️", key=f"wish_del_{w.id}"): delete_row(Wish, w.id); st.rerun()
            else: st.info("Add your first wish ✨")
        elif sec == "Vision Board":
            st.caption("Drop text, images, or videos — no forced captions/tags.")
            kind = st.radio("Add", ["Text","Image","Video"], horizontal=True)
            if kind == "Text":
                txt = st.text_area("Write something")
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
            else:
                url = st.text_input("YouTube/Video URL (or upload a video)")
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

            with SessionLocal() as s:
                cards = s.query(Board).order_by(Board.created_at.desc()).all()
            if cards:
                grid_cols = st.columns(3)
                for i, c in enumerate(cards):
                    with grid_cols[i % 3]:
                        if c.kind == "text":
                            st.markdown(f'<div class="minibox">{c.content}</div>', unsafe_allow_html=True)
                        elif c.kind == "image":
                            if c.media_path and os.path.exists(c.media_path): st.image(c.media_path, use_column_width=True)
                        else:
                            if c.content and c.content.startswith("http"): st.video(c.content)
                            elif c.media_path and os.path.exists(c.media_path): st.video(c.media_path)
                        if st.button("🗑️ Remove", key=f"vb_del_{c.id}"):
                            delete_row(Board, c.id)
                            if c.media_path and os.path.exists(c.media_path):
                                try: os.remove(c.media_path)
                                except: pass
                            st.rerun()
            else:
                st.info("Your board is empty — add a block above.")
        else:
            c1, c2, c3 = st.columns([0.4,0.3,0.3])
            with c1: place = st.text_input("Destination", key="t_place", placeholder="Kyoto")
            with c2: timeline = st.text_input("Target Timeline", key="t_time", placeholder="Oct 2025")
            with c3: status = st.selectbox("Status", ["Planned","Booked","Done"], index=0, key="t_status")
            notes = st.text_area("Notes", key="t_notes", placeholder="Accommodation ideas, must-do spots…")
            if st.button("Add Trip ➕", key="t_add"):
                with SessionLocal() as s:
                    s.add(Travel(user_id=get_user_by_name("Ravi").id,
                                 place=f"🧭 {place or 'Somewhere'}", timeline=timeline or "2025",
                                 status=status, notes=notes)); s.commit()
                st.success("Trip added."); st.rerun()
            with SessionLocal() as s:
                trips = s.query(Travel).order_by(Travel.status.asc()).all()
            if trips:
                df = pd.DataFrame([{"Destination": tr.place, "Timeline": tr.timeline, "Status": tr.status, "Notes": tr.notes, "ID": tr.id} for tr in trips])
                st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)
                del_id = st.selectbox("Remove a trip (optional)", options=["—"] + [str(tr.id) for tr in trips], key="t_del")
                if del_id != "—": delete_row(Travel, int(del_id)); st.rerun()
            else: st.info("Add your first travel plan ✈️")
    else:
        # Minimal To-Do for Ravi/Amitha
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

        # To-Do input (Enter to add)
        st.markdown("<div class='todo-input'>", unsafe_allow_html=True)
        key_input = f"new_task_{user.id}"
        def _add_on_enter():
            title = (st.session_state.get(key_input) or "").strip()
            if title:
                with SessionLocal() as s:
                    s.add(Task(user_id=user.id, title=f"{pick_emoji(title)} {title}",
                               scope="daily", due_date=st.session_state[key_date]))
                    s.commit()
                st.session_state[key_input] = ""
                st.rerun()
        st.text_input("Add a task", key=key_input, placeholder="Type and press Enter…",
                      on_change=_add_on_enter, label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)

        # Tasks list
        with SessionLocal() as s:
            tasks = s.query(Task).filter(Task.user_id==user.id, Task.scope=="daily",
                                         Task.due_date==st.session_state[key_date])\
                                 .order_by(Task.completed.asc(), Task.created_at.desc()).all()
        if not tasks:
            st.markdown("<div class='minibox'>No tasks yet — add one above ✨</div>", unsafe_allow_html=True)
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
                    st.markdown(f"**{t.title}**")
                with col3:
                    if st.button("🗑️", key=f"del_{t.id}"):
                        delete_row(Task, t.id); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)