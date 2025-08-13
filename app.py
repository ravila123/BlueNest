
import os
import re
import datetime as dt
from typing import Optional, List, Dict
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

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
    scope = Column(String, nullable=False)  # daily/weekly/monthly/quarterly/half/year
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
    __tablename__ = "vision_board"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    caption = Column(String, nullable=False)
    image_path = Column(String, nullable=True)  # cached uploads
    tag = Column(String, default="general")
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

class Food(Base):
    __tablename__ = "food_list"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    dish = Column(String, nullable=False)
    type = Column(String, default="Meal")  # Meal/Snack/Dessert/Drink
    when = Column(String, default="Any")   # Any/Weeknight/Weekend/Date-Night
    tried = Column(Boolean, default=False)
    user = relationship("User")

def init_db():
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        if not s.query(User).count():
            for n in DEFAULT_USERS:
                s.add(User(name=n))
            s.commit()

init_db()

SCOPES = ["daily", "weekly", "monthly", "quarterly", "half", "year"]

# ---------- Helpers ----------
def get_user_by_name(name: str) -> User:
    with SessionLocal() as s:
        u = s.query(User).filter(User.name == name).first()
        if not u:
            u = User(name=name)
            s.add(u); s.commit(); s.refresh(u)
        return u

def auto_rollover_incomplete_daily(user_id: int):
    today = dt.date.today()
    with SessionLocal() as s:
        stale = (
            s.query(Task)
            .filter(Task.user_id == user_id, Task.scope == "daily",
                    Task.completed == False, Task.due_date != None, Task.due_date < today)
            .all()
        )
        for t in stale: t.due_date = today
        if stale: s.commit()

def add_task(user_id: int, title: str, scope: str, due: Optional[dt.date], notes: str):
    with SessionLocal() as s:
        s.add(Task(user_id=user_id, title=title.strip(), scope=scope, due_date=due, notes=notes.strip()))
        s.commit()

def toggle_task(task_id: int, value: bool):
    with SessionLocal() as s:
        t = s.query(Task).get(task_id)
        if t:
            t.completed = value; s.commit()

def delete_row(model, row_id: int):
    with SessionLocal() as s:
        obj = s.query(model).get(row_id)
        if obj:
            s.delete(obj); s.commit()

def pick_emoji(text: str, scope: str) -> str:
    import re
    t = text.lower()
    scope_emoji = {"daily":"🗓️","weekly":"📆","monthly":"🗓️","quarterly":"📊","half":"🌓","year":"🎯"}.get(scope,"•")
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
        (r"\bcode|bug|deploy|commit\b","🧑‍💻"),
        (r"\bclean|laundry|dish|trash\b","🧹"),
        (r"\btravel|trip|itinerary\b","🧭"),
    ]
    for pat, emo in mapping:
        if re.search(pat, t): return emo
    return scope_emoji

def board_summary_for_user(uid: int) -> str:
    with SessionLocal() as s:
        cards = s.query(Board).filter(Board.user_id==uid).all()
        if not cards: return "No vision items yet."
        tags = {}
        for c in cards:
            k = (c.tag or "general").strip().lower()
            tags[k] = tags.get(k, 0) + 1
        parts = [f"#{k}: {v}" for k,v in sorted(tags.items(), key=lambda x:-x[1])]
        return " | ".join(parts)

def answer_query(q: str, uid_map):
    ql = q.lower().strip()
    who = None
    for name in uid_map:
        if name.lower() in ql:
            who = name
            break
    if who is None:
        who = list(uid_map.keys())[0]
    uid = uid_map[who]
    import re, datetime as dt
    with SessionLocal() as s:
        if "fitness" in ql:
            fit = s.query(Task).filter(Task.user_id==uid, Task.scope.in_(["year","half","quarterly","monthly"])).all()
            hits = [t for t in fit if re.search(r"run|gym|workout|yoga|lift|walk|swim|steps|marathon|cardio", (t.title + " " + (t.notes or "")).lower())]
            if hits:
                bullets = "\n".join([f"- {t.title}" for t in hits[:8]])
                return f"{who}'s fitness-focused goals:\n{bullets}"
            else:
                return f"I couldn't find explicit fitness goals for {who}. Try adding some under Year/Monthly tabs."
        if "travel" in ql or "trip" in ql:
            trips = s.query(Travel).filter(Travel.user_id==uid).all()
            if trips:
                bullets = "\n".join([f"- {tr.place} ({tr.timeline}) — {tr.status}" for tr in trips[:10]])
                return f"{who}'s travel plans:\n{bullets}"
            else:
                return f"No travel goals saved for {who} yet."
        if "year goal" in ql or "yearly" in ql:
            yg = s.query(Task).filter(Task.user_id==uid, Task.scope=="year").all()
            if yg:
                bullets = "\n".join([f"- {t.title}" for t in yg[:12]])
                return f"{who}'s year goals:\n{bullets}"
            else:
                return f"No year goals for {who} yet."
        today = dt.date.today()
        d = s.query(Task).filter(Task.user_id==uid, Task.scope=="daily", Task.due_date==today).all()
        if d:
            bullets = "\n".join([f"- {t.title} ({'Done' if t.completed else 'Pending'})" for t in d[:12]])
            return f"Today's tasks for {who}:\n{bullets}"
        return "Ask me about fitness goals, travel, or year goals — or include a name like 'Ravi' or 'Amitha'."

# ---------- UI ----------
st.set_page_config(page_title="BlueNest", page_icon="💙", layout="wide")

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
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### <div class='title-row'><span class='title-heart'>💙</span><span>BlueNest</span></div>", unsafe_allow_html=True)
    st.caption("A cozy, shared planner for Ravi & Amitha.")
    with SessionLocal() as s:
        user_names = [u.name for u in s.query(User).order_by(User.name).all()]
    for required in DEFAULT_USERS:
        if required not in user_names:
            get_user_by_name(required)
    with SessionLocal() as s:
        user_names = [u.name for u in s.query(User).order_by(User.name).all()]
    current_user_name = st.selectbox("Active User", options=user_names, index=user_names.index("Ravi") if "Ravi" in user_names else 0)
    current_user = get_user_by_name(current_user_name)

    st.markdown("---")
    st.write("**Quick Add (Daily To‑Do)**")
    q_title = st.text_input("Title", key="qa_title", placeholder="E.g., Book tickets, Prep lunch, Gym session")
    if st.button("Add to Today's List ➕", use_container_width=True):
        if q_title.strip():
            add_task(current_user.id, f"{pick_emoji(q_title, 'daily')} {q_title}", "daily", __import__('datetime').date.today(), "")
            st.success("Added!")
            st.rerun()

auto_rollover_incomplete_daily(current_user.id)

today = __import__('datetime').date.today()
st.markdown(f"## {APP_TITLE}")
st.caption(today.strftime('%A, %B %d, %Y'))

with st.expander("🐶 Ask BlueNest", expanded=False):
    with SessionLocal() as s:
        us = s.query(User).order_by(User.name).all()
        uid_map = {u.name: u.id for u in us}
    q = st.text_input("Ask a question about your goals, tasks, travel, or vision board")
    if q:
        ans = answer_query(q, uid_map)
        st.text(ans)

tabs = st.tabs([
    "Dashboard", "Daily", "Weekly", "Monthly", "Quarterly", "Half-Year", "Year",
    "Wish List", "Vision Board", "Travel", "Food", "Summary", "Settings"
])

def task_list_ui(scope: str):
    st.markdown(f"#### {scope.capitalize()} Planner")
    due = None
    if scope == "daily":
        due = st.date_input("For date", value=__import__('datetime').date.today(), key=f"date_{scope}")
    title = st.text_input("Add a task", key=f"title_{scope}", placeholder="Describe the task…")
    notes = st.text_area("Notes (optional)", key=f"notes_{scope}", placeholder="Any details…", height=80)
    if st.button(f"Add {scope.capitalize()} Task", key=f"add_{scope}"):
        if title.strip():
            title_with_emoji = f"{pick_emoji(title, scope)} {title}"
            add_task(current_user.id, title_with_emoji, scope, due, notes)
            st.success("Task added.")
            st.rerun()

    with SessionLocal() as s:
        q = s.query(Task).filter(Task.user_id == current_user.id, Task.scope == scope)
        if scope == "daily":
            chosen_day = st.session_state.get(f"date_{scope}", __import__('datetime').date.today())
            q = q.filter(Task.due_date == chosen_day)
        tasks = q.order_by(Task.completed.asc(), Task.created_at.desc()).all()

    if not tasks:
        st.info("No tasks yet — add one above ✨"); return

    for t in tasks:
        cols = st.columns([0.06, 0.74, 0.12, 0.08])
        with cols[0]:
            checked = st.checkbox("", value=t.completed, key=f"chk_{scope}_{t.id}")
            if checked != t.completed:
                toggle_task(t.id, checked); st.rerun()
        with cols[1]:
            label = f"**{t.title}**"
            if t.notes: label += f"<br/><span style='font-size:.85rem;opacity:.8'>{t.notes}</span>"
            if scope == "daily" and t.due_date:
                label += f" &nbsp; <span class='tag'>📅 {t.due_date.strftime('%b %d')}</span>"
            st.markdown(label, unsafe_allow_html=True)
        with cols[2]:
            st.markdown(f"<span class='tag'>{'✅ Done' if t.completed else '⏳ Pending'}</span>", unsafe_allow_html=True)
        with cols[3]:
            if st.button("🗑️", key=f"del_{scope}_{t.id}", help="Delete"):
                delete_row(Task, t.id); st.rerun()

# Dashboard
with tabs[0]:
    st.markdown("### Overview")
    with SessionLocal() as s:
        total_today = s.query(Task).filter(Task.user_id==current_user.id, Task.scope=="daily", Task.due_date==__import__('datetime').date.today()).count()
        done_today = s.query(Task).filter(Task.user_id==current_user.id, Task.scope=="daily", Task.due_date==__import__('datetime').date.today(), Task.completed==True).count()
        pct = int((done_today/total_today)*100) if total_today else 0
        st.markdown(f'<div class="bubble"><b>Hi, {current_user.name}!</b> You’ve completed <b>{done_today}</b> of <b>{total_today}</b> today — <b>{pct}%</b>. Keep going! 💪</div>', unsafe_allow_html=True)

        st.markdown("#### Vision Board Summary")
        if s.query(Board).filter(Board.user_id==current_user.id).count():
            st.markdown(f"<div class='bubble'>{board_summary_for_user(current_user.id)}</div>", unsafe_allow_html=True)
        else:
            st.info("No vision board items yet. Add a few under the Vision Board tab.")

        st.markdown("#### This Week Snapshot")
        week_end = __import__('datetime').date.today() + __import__('datetime').timedelta(days=6)
        week_tasks = s.query(Task).filter(Task.user_id==current_user.id, Task.scope=="daily",
                                          Task.due_date >= __import__('datetime').date.today(), Task.due_date <= week_end).all()
        if week_tasks:
            df = pd.DataFrame([{"Date": t.due_date, "Task": t.title, "Status": "Done" if t.completed else "Pending"} for t in week_tasks]).sort_values(["Date","Status"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No daily tasks scheduled for the next 7 days.")

# Scopes
with tabs[1]: task_list_ui("daily")
with tabs[2]: task_list_ui("weekly")
with tabs[3]: task_list_ui("monthly")
with tabs[4]: task_list_ui("quarterly")
with tabs[5]: task_list_ui("half")
with tabs[6]: task_list_ui("year")

# Wish List
with tabs[7]:
    st.markdown("#### Wish List")
    colA, colB, colC, colD = st.columns([0.38, 0.32, 0.18, 0.12])
    with colA: w_item = st.text_input("What do you want?", key="wish_item", placeholder="Noise-canceling headphones")
    with colB: w_link = st.text_input("Link (optional)", key="wish_link", placeholder="https://…")
    with colC: w_pri = st.selectbox("Priority", ["Low","Medium","High"], index=1, key="wish_pri")
    with colD:
        st.write("")
        if st.button("Add ➕", use_container_width=True, key="wish_add"):
            if w_item.strip():
                with SessionLocal() as s:
                    title = f"🎁 {w_item.strip()}"
                    s.add(Wish(user_id=current_user.id, item=title, link=w_link.strip(), priority=w_pri)); s.commit()
                st.success("Added to wish list."); st.rerun()

    with SessionLocal() as s:
        wishes = s.query(Wish).filter(Wish.user_id==current_user.id).order_by(Wish.acquired.asc(), Wish.priority.desc()).all()
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

# Vision Board
with tabs[8]:
    st.markdown("#### Vision Board")
    col1, col2 = st.columns([0.6, 0.4])
    with col1:
        v_caption = st.text_input("Caption", key="v_caption", placeholder="Run a half marathon")
        v_tag = st.text_input("Tag", key="v_tag", placeholder="health, career, travel…")
        v_img = st.file_uploader("Image (optional)", type=["png","jpg","jpeg","webp"], key="v_img")
        if st.button("Add to Board ➕", key="v_add"):
            img_path = None
            if v_img:
                upload_dir = "uploads"; os.makedirs(upload_dir, exist_ok=True)
                img_path = os.path.join(upload_dir, f"{__import__('time').time()}_{v_img.name}")
                with open(img_path,"wb") as f: f.write(v_img.read())
            with SessionLocal() as s:
                s.add(Board(user_id=current_user.id, caption=f"🪄 {v_caption or 'Untitled'}", image_path=img_path, tag=v_tag or 'general')); s.commit()
            st.success("Added to your board."); st.rerun()
    with col2:
        st.info("Tip: Tag your visions (e.g., health, career, travel) and filter below.")

    tag_filter = st.text_input("Filter by tag (optional)", key="v_filter")
    with SessionLocal() as s:
        q = s.query(Board).filter(Board.user_id==current_user.id)
        if tag_filter.strip(): q = q.filter(Board.tag.contains(tag_filter.strip()))
        cards = q.order_by(Board.id.desc()).all()

    if cards:
        grid_cols = st.columns(3)
        for i, c in enumerate(cards):
            with grid_cols[i % 3]:
                st.markdown(f"**{c.caption}**  \n<span class='tag'>#{c.tag}</span>", unsafe_allow_html=True)
                if c.image_path and os.path.exists(c.image_path): st.image(c.image_path, use_column_width=True)
                if st.button("🗑️ Remove", key=f"vb_del_{c.id}"):
                    delete_row(Board, c.id)
                    if c.image_path and os.path.exists(c.image_path):
                        try: os.remove(c.image_path)
                        except: pass
                    st.rerun()
    else: st.info("Pin your first vision ✨")

# Travel
with tabs[9]:
    st.markdown("#### Travel Goals")
    c1, c2, c3 = st.columns([0.4,0.3,0.3])
    with c1: place = st.text_input("Destination", key="t_place", placeholder="Kyoto")
    with c2: timeline = st.text_input("Target Timeline", key="t_time", placeholder="Oct 2025")
    with c3: status = st.selectbox("Status", ["Planned","Booked","Done"], index=0, key="t_status")
    notes = st.text_area("Notes", key="t_notes", placeholder="Accommodation ideas, must-do spots…")
    if st.button("Add Trip ➕", key="t_add"):
        with SessionLocal() as s:
            s.add(Travel(user_id=current_user.id, place=f"🧭 {place or 'Somewhere'}", timeline=timeline or "2025", status=status, notes=notes)); s.commit()
        st.success("Trip added."); st.rerun()

    with SessionLocal() as s:
        trips = s.query(Travel).filter(Travel.user_id==current_user.id).order_by(Travel.status.asc()).all()
    if trips:
        df = pd.DataFrame([{"Destination": tr.place, "Timeline": tr.timeline, "Status": tr.status, "Notes": tr.notes, "ID": tr.id} for tr in trips])
        st.dataframe(df.drop(columns=["ID"]), use_container_width=True, hide_index=True)
        del_id = st.selectbox("Remove a trip (optional)", options=["—"] + [str(tr.id) for tr in trips], key="t_del")
        if del_id != "—": delete_row(Travel, int(del_id)); st.rerun()
    else: st.info("Add your first travel plan ✈️")

# Food
with tabs[10]:
    st.markdown("#### Food List")
    f1,f2,f3,f4 = st.columns([0.4,0.2,0.2,0.2])
    with f1: dish = st.text_input("Dish/Item", key="f_dish", placeholder="Grilled chicken with quinoa")
    with f2: ftype = st.selectbox("Type", ["Meal","Snack","Dessert","Drink"], key="f_type")
    with f3: when = st.selectbox("When", ["Any","Weeknight","Weekend","Date-Night"], key="f_when")
    with f4:
        st.write("")
        if st.button("Add ➕", use_container_width=True, key="f_add"):
            with SessionLocal() as s:
                s.add(Food(user_id=current_user.id, dish=f"🍽️ {dish or 'Untitled'}", type=ftype, when=when)); s.commit()
            st.success("Added."); st.rerun()

    with SessionLocal() as s:
        foods = s.query(Food).filter(Food.user_id==current_user.id).order_by(Food.tried.asc(), Food.type.asc()).all()
    if foods:
        for fd in foods:
            cols = st.columns([0.06, 0.54, 0.22, 0.18])
            with cols[0]:
                tried = st.checkbox("", value=fd.tried, key=f"food_chk_{fd.id}")
                if tried != fd.tried:
                    with SessionLocal() as s:
                        fupd = s.query(Food).get(fd.id); fupd.tried = tried; s.commit()
                    st.rerun()
            with cols[1]: st.markdown(f"**{fd.dish}**", unsafe_allow_html=True)
            with cols[2]: st.markdown(f"<span class='tag'>{fd.type}</span>", unsafe_allow_html=True)
            with cols[3]:
                st.markdown(f"<span class='tag'>{fd.when}</span>", unsafe_allow_html=True)
                if st.button("🗑️", key=f"food_del_{fd.id}"): delete_row(Food, fd.id); st.rerun()
    else: st.info("Start your food ideas 🍽️")

# Summary (both users)
with tabs[11]:
    st.markdown("#### Shared Summary")
    with SessionLocal() as s:
        us = s.query(User).order_by(User.name).all()
        names = [u.name for u in us]; uid = {u.name: u.id for u in us}
        rows = []
        for nm in names:
            tid = uid[nm]
            total_t = s.query(Task).filter(Task.user_id==tid, Task.scope=="daily", Task.due_date==__import__('datetime').date.today()).count()
            done_t = s.query(Task).filter(Task.user_id==tid, Task.scope=="daily", Task.due_date==__import__('datetime').date.today(), Task.completed==True).count()
            pct = int((done_t/total_t)*100) if total_t else 0
            rows.append({"User": nm, "Today's Done": done_t, "Today's Total": total_t, "Progress %": pct})
        st.markdown("**Today at a glance**")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.markdown("**Year Goals (open)**")
        yg = s.query(Task).filter(Task.scope=="year", Task.completed==False).all()
        if yg:
            df = pd.DataFrame([{"User": s.query(User).get(t.user_id).name, "Goal": t.title, "Notes": (t.notes or "")[:120]} for t in yg])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else: st.info("No open year goals yet.")

        st.markdown("**Wish List — High Priority**")
        highs = s.query(Wish).filter(Wish.priority=="High", Wish.acquired==False).all()
        if highs:
            dfh = pd.DataFrame([{"User": s.query(User).get(w.user_id).name, "Item": w.item, "Link": w.link if (w.link and w.link.startswith('http')) else ""} for w in highs])
            st.dataframe(dfh, use_container_width=True, hide_index=True)
        else: st.info("No high-priority wishes pending.")

# Settings
with tabs[12]:
    st.markdown("#### Settings")
    st.markdown("Manage people so both of you show up in the dropdown:")
    with SessionLocal() as s: existing = [u.name for u in s.query(User).order_by(User.name).all()]
    colA, colB = st.columns(2)
    with colA:
        new_name = st.text_input("Add a user", placeholder="Type a name…")
        if st.button("Add User", key="user_add"):
            if new_name.strip() and new_name.strip() not in existing:
                with SessionLocal() as s: s.add(User(name=new_name.strip())); s.commit()
                st.success("User added."); st.rerun()
    with colB:
        rename_from = st.selectbox("Rename existing", options=existing)
        rename_to = st.text_input("New name")
        if st.button("Rename", key="user_rename"):
            with SessionLocal() as s:
                u = s.query(User).filter(User.name==rename_from).first()
                if u and rename_to.strip():
                    u.name = rename_to.strip(); s.commit()
            st.success("Renamed."); st.rerun()

    st.caption("Storage: SQLite `bluenest.db` next to the app; uploads in `uploads/`.")
