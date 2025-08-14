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
    updated_at = Column(DateTime, default=dt.datetime.utcnow)
    notes = Column(Text, default="")
    priority = Column(Integer, default=0)  # New field for ordering
    auto_rollover = Column(Boolean, default=True)  # New field for rollover behavior
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

class VisionBoardItem(Base):
    """Vision board items with position and content type fields"""
    __tablename__ = "vision_board_items"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    content_type = Column(String)  # "text", "image", "video", "link"
    content_data = Column(Text)
    position_x = Column(Integer, default=0)
    position_y = Column(Integer, default=0)
    width = Column(Integer, default=200)
    height = Column(Integer, default=150)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow)
    user = relationship("User")

class DashboardMetric(Base):
    """Dashboard metrics for tracking user insights"""
    __tablename__ = "dashboard_metrics"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    metric_type = Column(String)  # "goal", "completion_rate", "streak"
    metric_value = Column(String)
    date_recorded = Column(Date, default=dt.date.today)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    user = relationship("User")

def init_db():
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        if not s.query(User).count():
            for n in DEFAULT_USERS:
                s.add(User(name=n))
            s.commit()

# Initialize database
init_db()

# ---------- Dynamic Background System ----------
def get_daily_background_theme(date: dt.date) -> str:
    """Return CSS class name for daily background theme based on date"""
    themes = [
        "cosmic-blue", "aurora-green", "sunset-orange", 
        "deep-purple", "ocean-teal", "forest-emerald", "rose-gold"
    ]
    day_of_year = date.timetuple().tm_yday
    return themes[day_of_year % len(themes)]

def get_background_css(theme: str) -> str:
    """Generate CSS for the specified background theme"""
    theme_configs = {
        "cosmic-blue": {
            "gradient": "radial-gradient(circle at 20% 80%, rgba(120, 119, 198, 0.3), transparent 50%), radial-gradient(circle at 80% 20%, rgba(255, 119, 198, 0.15), transparent 50%), linear-gradient(135deg, #0f0f23 0%, #1a1a2e 100%)"
        },
        "aurora-green": {
            "gradient": "radial-gradient(circle at 30% 70%, rgba(34, 197, 94, 0.25), transparent 50%), radial-gradient(circle at 70% 30%, rgba(16, 185, 129, 0.15), transparent 50%), linear-gradient(135deg, #0a1f0a 0%, #1a2e1a 100%)"
        },
        "sunset-orange": {
            "gradient": "radial-gradient(circle at 25% 75%, rgba(251, 146, 60, 0.28), transparent 50%), radial-gradient(circle at 75% 25%, rgba(249, 115, 22, 0.18), transparent 50%), linear-gradient(135deg, #1f0f0a 0%, #2e1a0f 100%)"
        },
        "deep-purple": {
            "gradient": "radial-gradient(circle at 35% 65%, rgba(147, 51, 234, 0.26), transparent 50%), radial-gradient(circle at 65% 35%, rgba(126, 34, 206, 0.16), transparent 50%), linear-gradient(135deg, #1a0f1f 0%, #2e1a2e 100%)"
        },
        "ocean-teal": {
            "gradient": "radial-gradient(circle at 40% 60%, rgba(20, 184, 166, 0.24), transparent 50%), radial-gradient(circle at 60% 40%, rgba(13, 148, 136, 0.14), transparent 50%), linear-gradient(135deg, #0a1f1f 0%, #1a2e2e 100%)"
        },
        "forest-emerald": {
            "gradient": "radial-gradient(circle at 15% 85%, rgba(16, 185, 129, 0.27), transparent 50%), radial-gradient(circle at 85% 15%, rgba(5, 150, 105, 0.17), transparent 50%), linear-gradient(135deg, #0f1f0f 0%, #1a2e1a 100%)"
        },
        "rose-gold": {
            "gradient": "radial-gradient(circle at 45% 55%, rgba(244, 114, 182, 0.23), transparent 50%), radial-gradient(circle at 55% 45%, rgba(236, 72, 153, 0.13), transparent 50%), linear-gradient(135deg, #1f0f1a 0%, #2e1a2e 100%)"
        }
    }
    
    config = theme_configs.get(theme, theme_configs["cosmic-blue"])
    return f"background: {config['gradient']}; animation: backgroundShift 20s ease-in-out infinite;"

# ---------- Navigation System ----------
class NavigationState:
    """Manages active user and current view state"""
    def __init__(self):
        self.active_user: str = "Ravi"  # Default user
        self.current_view: str = "todo"  # Default view
    
    def set_active_user(self, user: str):
        """Set the active user and reset view to appropriate default"""
        self.active_user = user
        available_views = get_available_views(user)
        if self.current_view not in available_views:
            self.current_view = available_views[0] if available_views else "todo"
    
    def set_current_view(self, view: str):
        """Set the current view if it's available for the active user"""
        available_views = get_available_views(self.active_user)
        if view in available_views:
            self.current_view = view
    
    def get_state(self) -> dict:
        """Get current navigation state as dictionary"""
        return {
            "active_user": self.active_user,
            "current_view": self.current_view,
            "available_views": get_available_views(self.active_user)
        }

def get_available_views(user: str) -> List[str]:
    """Return context-appropriate view options based on selected user"""
    if user == "Common":
        return ["dashboard", "wishlist", "vision_board", "travel_goals"]
    else:  # Individual users (Ravi/Amitha)
        return ["todo", "dashboard"]

def initialize_navigation_state():
    """Initialize navigation state in session state if not exists"""
    if "nav_state" not in st.session_state:
        st.session_state.nav_state = NavigationState()
    return st.session_state.nav_state

# ---------- Microsoft Teams-style Todo Interface ----------
class TodoInterface:
    """Microsoft Teams-style todo interface with instant save functionality"""
    
    def __init__(self, user_id: int, date: dt.date):
        self.user_id = user_id
        self.date = date
        self._check_and_trigger_rollover()
    
    def render_task_input(self):
        """Render task input with instant save on Enter key press"""
        key_input = f"new_task_{self.user_id}_{self.date}"
        
        # Create input field with auto-save on change
        def handle_task_creation():
            title = (st.session_state.get(key_input) or "").strip()
            if title:
                self._save_task(title)
                st.session_state[key_input] = ""  # Clear input
                st.rerun()
        
        st.markdown("<div class='todo-input'>", unsafe_allow_html=True)
        st.text_input(
            "Add a task", 
            key=key_input, 
            placeholder="Add a new task...",
            on_change=handle_task_creation, 
            label_visibility="collapsed"
        )
        st.markdown("</div>", unsafe_allow_html=True)
    
    def _save_task(self, title: str):
        """Save task to database instantly"""
        with SessionLocal() as s:
            task = Task(
                user_id=self.user_id,
                title=title,
                scope="daily",
                due_date=self.date,
                updated_at=dt.datetime.utcnow()
            )
            s.add(task)
            s.commit()
    
    def render_task_list(self):
        """Render task list with click-to-edit functionality"""
        with SessionLocal() as s:
            tasks = s.query(Task).filter(
                Task.user_id == self.user_id,
                Task.scope == "daily",
                Task.due_date == self.date
            ).order_by(Task.completed.asc(), Task.created_at.desc()).all()
        
        if not tasks:
            st.markdown("<div style='color: rgba(255,255,255,0.4); font-style: italic; padding: 1rem 0;'>No tasks yet...</div>", unsafe_allow_html=True)
            return
        
        # Clean task list without any containers
        for task in tasks:
            self._render_task_item(task)
    
    def _render_task_item(self, task):
        """Render individual task item with inline editing"""
        # Add completed class for styling
        item_class = "todo-item completed" if task.completed else "todo-item"
        st.markdown(f"<div class='{item_class}'>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([0.06, 0.88, 0.06])
        
        with col1:
            # Minimal checkbox for completion
            checked = st.checkbox("", value=task.completed, key=f"chk_{task.id}", label_visibility="collapsed")
            if checked != task.completed:
                self._toggle_task_completion(task.id, checked)
                st.rerun()
        
        with col2:
            # Task title with click-to-edit functionality
            edit_key = f"edit_{task.id}"
            if edit_key not in st.session_state:
                st.session_state[edit_key] = False
            
            if st.session_state[edit_key]:
                # Edit mode
                col_input, col_save = st.columns([0.8, 0.2])
                with col_input:
                    new_title = st.text_input(
                        "",
                        value=task.title,
                        key=f"edit_input_{task.id}",
                        label_visibility="collapsed"
                    )
                with col_save:
                    if st.button("save", key=f"save_{task.id}"):
                        if new_title.strip():
                            self._update_task_title(task.id, new_title.strip())
                        st.session_state[edit_key] = False
                        st.rerun()
            else:
                # Display mode - clean task title
                if st.button(task.title, key=f"title_{task.id}", use_container_width=True):
                    st.session_state[edit_key] = True
                    st.rerun()
        
        with col3:
            # Minimal delete button
            if st.button("×", key=f"del_{task.id}", help="Delete task"):
                self._delete_task(task.id)
                st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    def _toggle_task_completion(self, task_id: int, completed: bool):
        """Toggle task completion status"""
        with SessionLocal() as s:
            task = s.query(Task).get(task_id)
            if task:
                task.completed = completed
                task.updated_at = dt.datetime.utcnow()
                s.commit()
    
    def _update_task_title(self, task_id: int, new_title: str):
        """Update task title"""
        with SessionLocal() as s:
            task = s.query(Task).get(task_id)
            if task:
                task.title = new_title
                task.updated_at = dt.datetime.utcnow()
                s.commit()
    
    def _delete_task(self, task_id: int):
        """Delete task"""
        with SessionLocal() as s:
            task = s.query(Task).get(task_id)
            if task:
                s.delete(task)
                s.commit()
    
    def _check_and_trigger_rollover(self):
        """Check if rollover should be triggered for this user and date"""
        # Only trigger rollover if viewing today's date or future dates
        if self.date >= dt.date.today():
            # Check if we need to process rollover for this user
            last_rollover_key = f"last_rollover_{self.user_id}"
            
            # Use session state to track last rollover date to avoid repeated processing
            if last_rollover_key not in st.session_state:
                st.session_state[last_rollover_key] = None
            
            # Only process rollover once per day per user
            if st.session_state[last_rollover_key] != dt.date.today():
                results = TaskRolloverManager.process_daily_rollover(self.user_id, dt.date.today())
                st.session_state[last_rollover_key] = dt.date.today()
                
                # Show rollover notification if tasks were rolled over
                if results["rolled_over"] > 0:
                    st.info(f"📋 {results['rolled_over']} incomplete task(s) rolled over from previous days")
    
    def get_rollover_summary(self) -> dict:
        """Get rollover summary for this user"""
        return TaskRolloverManager.get_rollover_insights(self.user_id)

# ---------- Task Auto-Rollover System ----------
class TaskRolloverHistory(Base):
    """Track rollover history for user insights"""
    __tablename__ = "task_rollover_history"
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    original_date = Column(Date, nullable=False)
    rolled_to_date = Column(Date, nullable=False)
    rollover_timestamp = Column(DateTime, default=dt.datetime.utcnow)
    task = relationship("Task")
    user = relationship("User")

class UserRolloverPreference(Base):
    """User preference settings for auto-rollover behavior"""
    __tablename__ = "user_rollover_preferences"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    auto_rollover_enabled = Column(Boolean, default=True)
    rollover_time_hours = Column(Integer, default=6)  # Hour of day to perform rollover (6 AM)
    rollover_incomplete_only = Column(Boolean, default=True)  # Only rollover incomplete tasks
    max_rollover_days = Column(Integer, default=7)  # Maximum days to keep rolling over a task
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow)
    user = relationship("User")

class TaskRolloverManager:
    """Manages task auto-rollover functionality"""
    
    @staticmethod
    def get_user_rollover_preference(user_id: int) -> UserRolloverPreference:
        """Get or create user rollover preference"""
        with SessionLocal() as session:
            preference = session.query(UserRolloverPreference).filter(
                UserRolloverPreference.user_id == user_id
            ).first()
            
            if not preference:
                preference = UserRolloverPreference(user_id=user_id)
                session.add(preference)
                session.commit()
                session.refresh(preference)
            
            return preference
    
    @staticmethod
    def should_rollover_task(task: Task, user_preference: UserRolloverPreference) -> bool:
        """Determine if a task should be rolled over"""
        if not user_preference.auto_rollover_enabled:
            return False
        
        if not task.auto_rollover:
            return False
        
        if task.completed:
            return False
        
        if user_preference.rollover_incomplete_only and task.completed:
            return False
        
        # Check if task has been rolled over too many times
        with SessionLocal() as session:
            rollover_count = session.query(TaskRolloverHistory).filter(
                TaskRolloverHistory.task_id == task.id
            ).count()
            
            if rollover_count >= user_preference.max_rollover_days:
                return False
        
        return True
    
    @staticmethod
    def rollover_task(task: Task, target_date: dt.date) -> bool:
        """Roll over a task to the target date"""
        try:
            with SessionLocal() as session:
                # Get the task from this session
                task_to_rollover = session.query(Task).get(task.id)
                if not task_to_rollover:
                    return False
                
                # Store original date for history
                original_date = task_to_rollover.due_date
                
                # Update task due date
                task_to_rollover.due_date = target_date
                task_to_rollover.updated_at = dt.datetime.utcnow()
                
                # Create rollover history entry
                history_entry = TaskRolloverHistory(
                    task_id=task_to_rollover.id,
                    user_id=task_to_rollover.user_id,
                    original_date=original_date,
                    rolled_to_date=target_date
                )
                session.add(history_entry)
                
                session.commit()
                return True
                
        except Exception as e:
            print(f"Error rolling over task {task.id}: {e}")
            return False
    
    @staticmethod
    def process_daily_rollover(user_id: int, current_date: dt.date) -> dict:
        """Process daily rollover for a user"""
        results = {
            "processed": 0,
            "rolled_over": 0,
            "skipped": 0,
            "errors": 0
        }
        
        try:
            user_preference = TaskRolloverManager.get_user_rollover_preference(user_id)
            
            if not user_preference.auto_rollover_enabled:
                return results
            
            with SessionLocal() as session:
                # Get incomplete tasks from previous days
                previous_date = current_date - dt.timedelta(days=1)
                
                incomplete_tasks = session.query(Task).filter(
                    Task.user_id == user_id,
                    Task.due_date < current_date,
                    Task.completed == False,
                    Task.scope == "daily",
                    Task.auto_rollover == True
                ).all()
                
                for task in incomplete_tasks:
                    results["processed"] += 1
                    
                    if TaskRolloverManager.should_rollover_task(task, user_preference):
                        if TaskRolloverManager.rollover_task(task, current_date):
                            results["rolled_over"] += 1
                        else:
                            results["errors"] += 1
                    else:
                        results["skipped"] += 1
                        
        except Exception as e:
            print(f"Error processing daily rollover for user {user_id}: {e}")
            results["errors"] += 1
        
        return results
    
    @staticmethod
    def get_rollover_history(user_id: int, days: int = 30) -> List[TaskRolloverHistory]:
        """Get rollover history for a user"""
        with SessionLocal() as session:
            cutoff_date = dt.date.today() - dt.timedelta(days=days)
            
            history = session.query(TaskRolloverHistory).filter(
                TaskRolloverHistory.user_id == user_id,
                TaskRolloverHistory.rollover_timestamp >= cutoff_date
            ).order_by(TaskRolloverHistory.rollover_timestamp.desc()).all()
            
            return history
    
    @staticmethod
    def get_rollover_insights(user_id: int) -> dict:
        """Get rollover insights for dashboard"""
        with SessionLocal() as session:
            # Get rollover history for the last 30 days
            thirty_days_ago = dt.date.today() - dt.timedelta(days=30)
            
            total_rollovers = session.query(TaskRolloverHistory).filter(
                TaskRolloverHistory.user_id == user_id,
                TaskRolloverHistory.rollover_timestamp >= thirty_days_ago
            ).count()
            
            # Get most frequently rolled over tasks
            from sqlalchemy import func
            frequent_rollovers = session.query(
                Task.title,
                func.count(TaskRolloverHistory.id).label('rollover_count')
            ).join(TaskRolloverHistory).filter(
                Task.user_id == user_id,
                TaskRolloverHistory.rollover_timestamp >= thirty_days_ago
            ).group_by(Task.id).order_by(func.count(TaskRolloverHistory.id).desc()).limit(5).all()
            
            return {
                "total_rollovers_30_days": total_rollovers,
                "frequent_rollovers": frequent_rollovers,
                "rollover_enabled": TaskRolloverManager.get_user_rollover_preference(user_id).auto_rollover_enabled
            }

def trigger_daily_rollover_check():
    """Trigger daily rollover check for all users"""
    try:
        with SessionLocal() as session:
            users = session.query(User).all()
            current_date = dt.date.today()
            
            rollover_results = {}
            
            for user in users:
                results = TaskRolloverManager.process_daily_rollover(user.id, current_date)
                rollover_results[user.name] = results
            
            return rollover_results
            
    except Exception as e:
        print(f"Error in daily rollover check: {e}")
        return {}

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

# ---------- Swipe Navigation System ----------
def get_swipe_navigation_js(user_id: int) -> str:
    """Generate JavaScript code for swipe navigation with touch event handling"""
    return f"""
    <script>
    (function() {{
        let startX = 0;
        let startY = 0;
        let startTime = 0;
        let isSwipeActive = false;
        let lastSwipeTime = 0;
        
        // Configuration
        const SWIPE_THRESHOLD = 50; // minimum distance for swipe
        const SWIPE_VELOCITY_THRESHOLD = 0.3; // minimum velocity
        const MAX_VERTICAL_DEVIATION = 100; // max vertical movement allowed
        const SWIPE_TIMEOUT = 300; // max time for swipe gesture
        const SWIPE_COOLDOWN = 1000; // prevent rapid swipes
        
        // Visual feedback elements
        let swipeIndicator = null;
        
        function createSwipeIndicator() {{
            if (swipeIndicator) return;
            
            swipeIndicator = document.createElement('div');
            swipeIndicator.style.cssText = `
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: rgba(56, 189, 248, 0.9);
                color: white;
                padding: 12px 20px;
                border-radius: 25px;
                font-size: 16px;
                font-weight: 600;
                z-index: 10000;
                opacity: 0;
                transition: opacity 0.3s ease;
                pointer-events: none;
                backdrop-filter: blur(10px);
                box-shadow: 0 4px 20px rgba(56, 189, 248, 0.3);
            `;
            document.body.appendChild(swipeIndicator);
        }}
        
        function showSwipeIndicator(direction) {{
            createSwipeIndicator();
            const arrow = direction === 'next' ? '→' : '←';
            const action = direction === 'next' ? 'Next Day' : 'Previous Day';
            swipeIndicator.innerHTML = `${{arrow}} ${{action}}`;
            swipeIndicator.style.opacity = '1';
            
            setTimeout(() => {{
                if (swipeIndicator) {{
                    swipeIndicator.style.opacity = '0';
                }}
            }}, 1200);
        }}
        
        function triggerSwipeNavigation(direction) {{
            const now = Date.now();
            if (now - lastSwipeTime < SWIPE_COOLDOWN) return;
            
            lastSwipeTime = now;
            showSwipeIndicator(direction);
            
            // Trigger Streamlit rerun by simulating button click
            const buttons = document.querySelectorAll('button');
            const targetButton = direction === 'prev' ? 
                Array.from(buttons).find(btn => btn.textContent.includes('←')) :
                Array.from(buttons).find(btn => btn.textContent.includes('→'));
            
            if (targetButton && !targetButton.disabled) {{
                targetButton.click();
            }} else {{
                // Show limitation message
                const limitMsg = direction === 'prev' ? 
                    'Use calendar for dates older than 7 days' :
                    'Cannot navigate more than 7 days ahead';
                
                swipeIndicator.innerHTML = `⚠️ ${{limitMsg}}`;
                swipeIndicator.style.background = 'rgba(239, 68, 68, 0.9)';
                setTimeout(() => {{
                    if (swipeIndicator) {{
                        swipeIndicator.style.background = 'rgba(56, 189, 248, 0.9)';
                    }}
                }}, 2000);
            }}
        }}
        
        function handleTouchStart(e) {{
            if (e.touches.length !== 1) return;
            
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
            startTime = Date.now();
            isSwipeActive = true;
        }}
        
        function handleTouchMove(e) {{
            if (!isSwipeActive || e.touches.length !== 1) return;
            
            // Prevent default scrolling during potential swipe
            const deltaX = Math.abs(e.touches[0].clientX - startX);
            const deltaY = Math.abs(e.touches[0].clientY - startY);
            
            if (deltaX > deltaY && deltaX > 20) {{
                e.preventDefault();
            }}
        }}
        
        function handleTouchEnd(e) {{
            if (!isSwipeActive) return;
            
            const endX = e.changedTouches[0].clientX;
            const endY = e.changedTouches[0].clientY;
            const endTime = Date.now();
            
            const deltaX = endX - startX;
            const deltaY = Math.abs(endY - startY);
            const deltaTime = endTime - startTime;
            const velocity = Math.abs(deltaX) / deltaTime;
            
            isSwipeActive = false;
            
            // Check if this qualifies as a swipe
            if (Math.abs(deltaX) > SWIPE_THRESHOLD && 
                deltaY < MAX_VERTICAL_DEVIATION && 
                deltaTime < SWIPE_TIMEOUT && 
                velocity > SWIPE_VELOCITY_THRESHOLD) {{
                
                const direction = deltaX > 0 ? 'prev' : 'next';
                triggerSwipeNavigation(direction);
            }}
        }}
        
        // Add event listeners only to the main content area
        const mainContent = document.querySelector('[data-testid="stAppViewContainer"]');
        if (mainContent) {{
            mainContent.addEventListener('touchstart', handleTouchStart, {{ passive: false }});
            mainContent.addEventListener('touchmove', handleTouchMove, {{ passive: false }});
            mainContent.addEventListener('touchend', handleTouchEnd, {{ passive: true }});
        }}
        
        // Cleanup function
        window.addEventListener('beforeunload', function() {{
            if (swipeIndicator) {{
                document.body.removeChild(swipeIndicator);
            }}
        }});
    }})();
    </script>
    """

def handle_swipe_navigation(user_id: int, direction: str, current_date: dt.date) -> tuple[dt.date, bool, str]:
    """
    Handle swipe navigation with 7-day limit and return new date, success status, and message
    
    Args:
        user_id: Current user ID
        direction: 'next' or 'prev'
        current_date: Current date being viewed
        
    Returns:
        tuple of (new_date, success, message)
    """
    today = dt.date.today()
    
    if direction == 'next':
        new_date = current_date + dt.timedelta(days=1)
        # Check if new date is within 7 days forward from today
        days_from_today = (new_date - today).days
        if days_from_today > 7:
            return current_date, False, "Cannot navigate more than 7 days into the future"
        return new_date, True, f"Moved to {new_date.strftime('%A, %B %d')}"
        
    elif direction == 'prev':
        new_date = current_date - dt.timedelta(days=1)
        # Check if new date is within 7 days backward from today
        days_from_today = (today - new_date).days
        if days_from_today > 7:
            return current_date, False, "Cannot navigate more than 7 days into the past. Use calendar picker for older dates."
        return new_date, True, f"Moved to {new_date.strftime('%A, %B %d')}"
    
    return current_date, False, "Invalid direction"

# ---------- UI ----------
st.set_page_config(page_title="BlueNest", page_icon="💙", layout="wide")

# Dynamic background with daily themes and smooth animations
today = dt.date.today()
current_theme = get_daily_background_theme(today)
background_css = get_background_css(current_theme)

# Create CSS with dynamic background
css_content = """
<style>
@keyframes backgroundShift {
    0%, 100% { filter: hue-rotate(0deg) brightness(1); }
    25% { filter: hue-rotate(15deg) brightness(1.05); }
    50% { filter: hue-rotate(30deg) brightness(0.95); }
    75% { filter: hue-rotate(15deg) brightness(1.02); }
}

@keyframes subtleFloat {
    0%, 100% { transform: translateY(0px) scale(1); }
    50% { transform: translateY(-3px) scale(1.01); }
}

html, body, [data-testid="stAppViewContainer"] {
  """ + background_css + """
  transition: all 0.8s ease-in-out;
}"""

css_content += """
.block-container { 
  padding-top: 0.8rem; 
  padding-bottom: 1.6rem;
  animation: subtleFloat 8s ease-in-out infinite;
}
h1, h2, h3 { 
  letter-spacing: .2px;
  transition: all 0.3s ease;
}
.small { 
  opacity:.7; 
  font-size:.9rem;
  transition: opacity 0.3s ease;
}"""

css_content += """

/* Navigation Enhancements */
.stRadio > div {
  gap: 0.5rem;
}

.stRadio > div > label {
  background: rgba(17,24,39,0.4);
  border: 1px solid rgba(56,189,248,0.2);
  border-radius: 8px;
  padding: 0.5rem 0.8rem;
  margin: 0.2rem 0;
  transition: all 0.3s ease;
  cursor: pointer;
  backdrop-filter: blur(4px);
}

.stRadio > div > label:hover {
  border-color: rgba(56,189,248,0.4);
  background: rgba(17,24,39,0.6);
  transform: translateX(2px);
}

.stRadio > div > label[data-checked="true"] {
  border-color: rgba(56,189,248,0.6);
  background: rgba(56,189,248,0.1);
  box-shadow: 0 0 0 2px rgba(56,189,248,0.2);
}

/* View Content Transitions */
.main-content {
  animation: fadeInUp 0.4s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Sidebar Styling */
.css-1d391kg {
  background: rgba(17,24,39,0.3);
  border-right: 1px solid rgba(56,189,248,0.2);
  backdrop-filter: blur(8px);
}

/* Minimal Notebook-style Todo Interface */
.todo-input {
  margin-bottom: 1.5rem;
}
.todo-input input {
  background: transparent !important;
  border: none !important;
  border-bottom: 1px solid rgba(255,255,255,0.15) !important;
  border-radius: 0 !important;
  height: 36px; 
  font-size: 1rem;
  padding: 8px 0 !important;
  transition: border-color 0.2s ease !important;
  color: rgba(255,255,255,0.95) !important;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  width: 100% !important;
}
.todo-input input:focus {
  border-bottom-color: rgba(56,189,248,0.4) !important;
  box-shadow: none !important;
  background: transparent !important;
  outline: none !important;
}
.todo-input input::placeholder {
  color: rgba(255,255,255,0.4) !important;
  font-style: italic;
}

.todo-item {
  display: flex; 
  align-items: center; 
  gap: 0.6rem;
  padding: 0.4rem 0;
  margin-bottom: 0.1rem;
  border: none;
  background: transparent;
  transition: opacity 0.2s ease;
  min-height: 32px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.todo-item:hover {
  opacity: 0.8;
  border-bottom-color: rgba(255,255,255,0.1);
}
.todo-item:last-child {
  border-bottom: none;
}

/* Minimal checkbox styling */
.todo-item input[type="checkbox"] {
  width: 16px !important;
  height: 16px !important;
  margin: 0 !important;
  accent-color: rgba(56,189,248,0.8) !important;
}

/* Clean task title buttons */
.todo-item button[data-testid="baseButton-secondary"] {
  background: transparent !important;
  border: none !important;
  color: rgba(255,255,255,0.9) !important;
  text-align: left !important;
  padding: 0 !important;
  font-size: 1rem !important;
  line-height: 1.5 !important;
  transition: color 0.2s ease !important;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  text-decoration: none !important;
  box-shadow: none !important;
}
.todo-item button[data-testid="baseButton-secondary"]:hover {
  color: rgba(56,189,248,0.8) !important;
  background: transparent !important;
  text-decoration: underline !important;
  text-decoration-color: rgba(56,189,248,0.3) !important;
}

/* Completed task styling */
.todo-item.completed button[data-testid="baseButton-secondary"] {
  color: rgba(255,255,255,0.5) !important;
  text-decoration: line-through !important;
  text-decoration-color: rgba(255,255,255,0.3) !important;
}

/* Edit mode input styling */
.todo-item input[type="text"] {
  background: transparent !important;
  border: none !important;
  border-bottom: 1px solid rgba(56,189,248,0.4) !important;
  border-radius: 0 !important;
  padding: 4px 0 !important;
  color: rgba(255,255,255,0.95) !important;
  font-size: 1rem !important;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
}

/* Minimal save button */
.todo-item button[data-testid="baseButton-primary"] {
  background: transparent !important;
  border: none !important;
  color: rgba(56,189,248,0.8) !important;
  padding: 2px 6px !important;
  font-size: 0.8rem !important;
  transition: color 0.2s ease !important;
  text-decoration: underline !important;
}
.todo-item button[data-testid="baseButton-primary"]:hover {
  color: rgba(56,189,248,1) !important;
  background: transparent !important;
}

/* Minimal delete button */
.todo-item button[title="Delete task"] {
  background: transparent !important;
  border: none !important;
  color: rgba(255,255,255,0.25) !important;
  font-size: 1.1rem !important;
  padding: 0 !important;
  width: 20px !important;
  height: 20px !important;
  min-width: 20px !important;
  transition: color 0.2s ease !important;
  cursor: pointer !important;
  font-weight: 300 !important;
  line-height: 1 !important;
}
.todo-item button[title="Delete task"]:hover {
  color: rgba(239,68,68,0.7) !important;
  background: transparent !important;
  transform: none !important;
}
.todo-date { 
  font-size:.95rem; 
  opacity:.85; 
  letter-spacing:.2px;
  transition: all 0.3s ease;
}"""

css_content += """

.right-sticky { 
  position: sticky; 
  top: 6px; 
  z-index: 100;
  transition: all 0.3s ease;
}
.right-row { 
  display:flex; 
  justify-content:flex-end; 
  align-items:center; 
  gap:.4rem;
}
.right-row .dogbtn button {
  border-radius: 999px; 
  width: 40px; 
  height: 40px; 
  font-size: 20px;
  border: 1px solid rgba(56,189,248,.35); 
  background: rgba(17,24,39,.55);
  transition: all 0.3s ease;
  backdrop-filter: blur(8px);
}
.right-row .dogbtn button:hover {
  border-color: rgba(56,189,248,.55);
  background: rgba(17,24,39,.75);
  transform: scale(1.05);
}
.chatbox {
  background: rgba(17,24,39,.92);
  border:1px solid rgba(56,189,248,.30);
  border-radius: 12px; 
  padding: 10px; 
  width: 300px;
  box-shadow: 0 10px 28px rgba(2,132,199,.22);
  margin-left: auto;
  backdrop-filter: blur(12px);
  animation: slideInFromRight 0.4s ease-out;
}
@keyframes slideInFromRight {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
.quiet-divider { height: 8px; }

/* Swipe Navigation Enhancements */
.swipe-area {
  touch-action: pan-y pinch-zoom;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

.date-navigation {
  position: relative;
  transition: all 0.3s ease;
}

.date-navigation.swipe-feedback {
  transform: scale(1.02);
  box-shadow: 0 0 20px rgba(56, 189, 248, 0.3);
}

/* Enhanced date display with swipe hints */
.todo-date {
  position: relative;
  transition: all 0.3s ease;
  cursor: pointer;
}

.todo-date::after {
  content: "← swipe →";
  position: absolute;
  bottom: -18px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.7rem;
  opacity: 0.4;
  color: rgba(56, 189, 248, 0.6);
  transition: opacity 0.3s ease;
}

.todo-date:hover::after {
  opacity: 0.8;
}

/* Navigation button enhancements */
.nav-button-disabled {
  opacity: 0.3 !important;
  cursor: not-allowed !important;
}

.nav-button-enabled {
  transition: all 0.2s ease;
}

.nav-button-enabled:hover {
  transform: scale(1.1);
  background: rgba(56, 189, 248, 0.2) !important;
}
</style>
"""

st.markdown(css_content, unsafe_allow_html=True)

# Add swipe navigation JavaScript (will be called in todo view)
# st.markdown(get_swipe_navigation_js(), unsafe_allow_html=True)

# Initialize navigation state
nav_state = initialize_navigation_state()

# Enhanced Navigation Sidebar
with st.sidebar:
    st.markdown("### BlueNest 💙")
    st.caption("Navigate your productivity space")

    # ensure Ravi & Amitha exist
    with SessionLocal() as s:
        user_names = [u.name for u in s.query(User).order_by(User.name).all()]
    for required in DEFAULT_USERS:
        if required not in user_names:
            get_user_by_name(required)
    with SessionLocal() as s:
        user_names = [u.name for u in s.query(User).order_by(User.name).all()]

    # Active User Selector (including Common)
    st.markdown("#### Active User")
    user_options = DEFAULT_USERS + ["Common"]
    current_user_index = user_options.index(nav_state.active_user) if nav_state.active_user in user_options else 0
    
    selected_user = st.radio(
        "Select user context",
        options=user_options,
        index=current_user_index,
        horizontal=False,
        label_visibility="collapsed",
        key="user_selector"
    )
    
    # Update navigation state if user changed
    if selected_user != nav_state.active_user:
        nav_state.set_active_user(selected_user)
        st.rerun()
    
    # Context-sensitive view options
    st.markdown("#### Views")
    available_views = get_available_views(nav_state.active_user)
    
    # View display names mapping
    view_names = {
        "todo": "📝 To-Do List",
        "dashboard": "📊 Dashboard", 
        "wishlist": "🎯 Wishlist",
        "vision_board": "🎨 Vision Board",
        "travel_goals": "✈️ Travel Goals"
    }
    
    # Create view selector
    view_options = [view_names.get(view, view.title()) for view in available_views]
    current_view_index = available_views.index(nav_state.current_view) if nav_state.current_view in available_views else 0
    
    selected_view_display = st.radio(
        "Select view",
        options=view_options,
        index=current_view_index,
        label_visibility="collapsed",
        key="view_selector"
    )
    
    # Map back to internal view name
    selected_view = None
    for view, display_name in view_names.items():
        if display_name == selected_view_display:
            selected_view = view
            break
    
    # Update navigation state if view changed
    if selected_view and selected_view != nav_state.current_view:
        nav_state.set_current_view(selected_view)
        st.rerun()
    
    # Display current context info
    st.markdown("---")
    st.caption(f"**Context:** {nav_state.active_user}")
    st.caption(f"**View:** {nav_state.current_view.replace('_', ' ').title()}")
    
    # Rollover settings for individual users
    if nav_state.active_user != "Common":
        with st.expander("⚙️ Auto-Rollover Settings"):
            current_user = get_user_by_name(nav_state.active_user)
            try:
                preference = TaskRolloverManager.get_user_rollover_preference(current_user.id)
            except Exception:
                # If tables don't exist yet, create them and try again
                Base.metadata.create_all(engine)
                preference = TaskRolloverManager.get_user_rollover_preference(current_user.id)
            
            # Auto-rollover toggle
            auto_rollover = st.checkbox(
                "Enable auto-rollover", 
                value=preference.auto_rollover_enabled,
                help="Automatically move incomplete tasks to the next day"
            )
            
            # Max rollover days
            max_days = st.slider(
                "Max rollover days", 
                min_value=1, 
                max_value=14, 
                value=preference.max_rollover_days,
                help="Maximum days to keep rolling over a task"
            )
            
            # Save settings button
            if st.button("Save Settings", key="save_rollover_settings"):
                with SessionLocal() as s:
                    pref = s.query(UserRolloverPreference).filter(
                        UserRolloverPreference.user_id == current_user.id
                    ).first()
                    if pref:
                        pref.auto_rollover_enabled = auto_rollover
                        pref.max_rollover_days = max_days
                        pref.updated_at = dt.datetime.utcnow()
                        s.commit()
                        st.success("Settings saved!")
                        st.rerun()

# Set persona for backward compatibility with existing code
persona = nav_state.active_user if nav_state.active_user != "Common" else "Ravi"

today = dt.date.today()

# Dynamic header based on current view and user
view_titles = {
    "todo": f"📝 Daily Tasks - {nav_state.active_user}",
    "dashboard": f"📊 Dashboard - {nav_state.active_user}",
    "wishlist": "🎯 Shared Wishlist",
    "vision_board": "🎨 Vision Board",
    "travel_goals": "✈️ Travel Goals"
}

current_title = view_titles.get(nav_state.current_view, APP_TITLE)
st.markdown(f"## {current_title}")
st.caption(today.strftime('%A, %B %d, %Y'))

# ---------- Context-sensitive Layout ----------
if nav_state.current_view == "todo":
    # Two columns layout for to-do view (existing layout)
    left, right = st.columns([0.66, 0.34], gap="large")
else:
    # Single column layout for other views
    left = st.container()
    right = st.container()

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

# Show right panel only for to-do view
if nav_state.current_view == "todo":
    pass  # Right panel already handled above in the to-do view section
else:
    # For non-todo views, show a minimal right panel with just Ask Blue
    with right:
        st.markdown("<div class='right-sticky'>", unsafe_allow_html=True)
        row_l, row_r = st.columns([0.55, 0.45])
        with row_r:
            st.markdown("<div class='right-row'>", unsafe_allow_html=True)
            if "show_blue" not in st.session_state: st.session_state.show_blue = False
            with st.container():
                if st.button("🐶", key="blueboy_toggle_alt", help="Ask Blue", use_container_width=False):
                    st.session_state.show_blue = not st.session_state.show_blue
            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.show_blue:
            st.markdown("<div class='chatbox'>", unsafe_allow_html=True)
            st.markdown("**Hey! It's Blue boy!!**  \n*what do you want to know from me?*")
            default_user = persona
            q = st.text_input("Ask about a date", key="blue_q_alt", label_visibility="collapsed",
                              placeholder="e.g., what did I do on April 10?")
            if q:
                ans = ask_bluenest_summarizer(q, default_user)
                st.markdown(ans.replace("\n","  \n"))
            if st.button("Close", key="blue_close_alt", use_container_width=True):
                st.session_state.show_blue = False
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)  # Close main-content

# ========== MAIN CONTENT AREA - Context Sensitive ==========
st.markdown("<div class='main-content'>", unsafe_allow_html=True)

if nav_state.current_view == "todo":
    # ========== TO-DO VIEW ==========
    with left:
        user = get_user_by_name(persona)

        # Enhanced date state + controls with swipe navigation
        key_date = f"todo_date_{user.id}"
        if key_date not in st.session_state:
            st.session_state[key_date] = today

        # Add swipe navigation JavaScript for this user
        st.markdown(get_swipe_navigation_js(user.id), unsafe_allow_html=True)

        d: dt.date = st.session_state[key_date]
        
        # Enhanced navigation with swipe area
        st.markdown("<div class='swipe-area date-navigation'>", unsafe_allow_html=True)
        c_top = st.columns([0.12, 0.48, 0.40])
        
        with c_top[0]:
            # Enhanced previous button with 7-day limit
            days_back = (today - d).days
            can_prev = days_back < 7
            prev_class = "nav-button-enabled" if can_prev else "nav-button-disabled"
            
            if st.button("←", disabled=not can_prev, key=f"prev_{user.id}", 
                        help="Previous day (swipe right)" if can_prev else "Use calendar for dates older than 7 days"):
                new_date, success, message = handle_swipe_navigation(user.id, "prev", d)
                if success:
                    st.session_state[key_date] = new_date
                    st.rerun()
                else:
                    st.warning(message)
        
        with c_top[1]:
            # Enhanced date display with swipe hints
            st.markdown(f"<div class='todo-date'><b>{d.strftime('%A, %B %d')}</b></div>", unsafe_allow_html=True)
        
        with c_top[2]:
            # Enhanced next button with 7-day limit  
            days_forward = (d - today).days
            can_next = days_forward < 7
            next_class = "nav-button-enabled" if can_next else "nav-button-disabled"
            
            if st.button("→", disabled=not can_next, key=f"next_{user.id}",
                        help="Next day (swipe left)" if can_next else "Cannot navigate more than 7 days ahead"):
                new_date, success, message = handle_swipe_navigation(user.id, "next", d)
                if success:
                    st.session_state[key_date] = new_date
                    st.rerun()
                else:
                    st.warning(message)
        
        # Calendar picker for dates older than 7 days
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Show calendar picker with enhanced messaging
        col1, col2 = st.columns([0.7, 0.3])
        with col1:
            if days_back >= 7 or days_forward >= 7:
                st.info("📅 Use the calendar picker below for dates beyond the 7-day swipe range")
        with col2:
            pick = st.date_input("Pick date", value=d, label_visibility="collapsed", key=f"pick_{user.id}",
                               help="Calendar picker for any date")
            if pick != d:
                st.session_state[key_date] = pick
                st.rerun()

        # Microsoft Teams-style To-Do interface with instant save
        todo_interface = TodoInterface(user.id, st.session_state[key_date])
        todo_interface.render_task_input()
        todo_interface.render_task_list()

elif nav_state.current_view == "dashboard":
    # ========== DASHBOARD VIEW ==========
    with left:
        st.markdown("### 📊 Dashboard Overview")
        
        if nav_state.active_user == "Common":
            st.markdown("#### Shared Insights")
            st.info("Dashboard showing combined insights for all users")
            
            # Placeholder for shared dashboard content
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Tasks This Week", "42", "↑ 12%")
                st.metric("Vision Board Items", "8", "↑ 2")
            with col2:
                st.metric("Completed Goals", "3", "↑ 1")
                st.metric("Travel Plans", "2", "→ 0")
        else:
            st.markdown(f"#### {nav_state.active_user}'s Insights")
            st.info(f"Personal dashboard for {nav_state.active_user}")
            
            # Placeholder for personal dashboard content
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Tasks Completed Today", "5", "↑ 2")
                st.metric("Weekly Completion Rate", "78%", "↑ 5%")
            with col2:
                st.metric("Current Streak", "7 days", "↑ 1")
                st.metric("Monthly Goals", "2/5", "→ 0")

elif nav_state.current_view == "wishlist":
    # ========== WISHLIST VIEW ==========
    with left:
        st.markdown("### 🎯 Shared Wishlist")
        st.info("Manage shared wishes and goals for both users")
        
        # Placeholder wishlist interface
        new_wish = st.text_input("Add a new wish", placeholder="What would you like to add to the wishlist?")
        if st.button("Add Wish") and new_wish:
            st.success(f"Added: {new_wish}")
        
        st.markdown("#### Current Wishes")
        wishes = ["Weekend getaway to mountains", "New coffee machine", "Learn photography together"]
        for i, wish in enumerate(wishes):
            col1, col2 = st.columns([0.9, 0.1])
            with col1:
                st.markdown(f"• {wish}")
            with col2:
                if st.button("✓", key=f"wish_{i}"):
                    st.success("Wish completed!")

elif nav_state.current_view == "vision_board":
    # ========== VISION BOARD VIEW ==========
    with left:
        st.markdown("### 🎨 Vision Board")
        st.info("Create and manage your shared vision board - drag and drop images, videos, or add text")
        
        # File upload for vision board
        uploaded_files = st.file_uploader(
            "Upload images or videos",
            accept_multiple_files=True,
            type=['png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov']
        )
        
        if uploaded_files:
            st.markdown("#### Uploaded Content")
            cols = st.columns(3)
            for i, file in enumerate(uploaded_files):
                with cols[i % 3]:
                    if file.type.startswith('image'):
                        st.image(file, caption=file.name, use_column_width=True)
                    else:
                        st.video(file)
        
        # Text content for vision board
        st.markdown("#### Vision Text")
        vision_text = st.text_area("Add inspirational text or goals", 
                                 placeholder="Write your vision, goals, or inspirational quotes here...")
        if st.button("Save Vision Text") and vision_text:
            st.success("Vision text saved!")

elif nav_state.current_view == "travel_goals":
    # ========== TRAVEL GOALS VIEW ==========
    with left:
        st.markdown("### ✈️ Travel Goals")
        st.info("Plan and track your travel dreams and destinations")
        
        # Add new travel goal
        col1, col2 = st.columns([0.7, 0.3])
        with col1:
            new_destination = st.text_input("Destination", placeholder="Where do you want to go?")
        with col2:
            target_date = st.date_input("Target Date", value=today + dt.timedelta(days=365))
        
        if st.button("Add Travel Goal") and new_destination:
            st.success(f"Added travel goal: {new_destination}")
        
        st.markdown("#### Planned Destinations")
        destinations = [
            {"place": "Japan - Cherry Blossom Season", "date": "April 2025", "status": "Planning"},
            {"place": "Iceland - Northern Lights", "date": "December 2025", "status": "Researching"},
            {"place": "New Zealand - Adventure Trip", "date": "March 2026", "status": "Dreaming"}
        ]
        
        for dest in destinations:
            with st.expander(f"{dest['place']} - {dest['date']}"):
                st.markdown(f"**Status:** {dest['status']}")
                st.text_area("Notes", placeholder="Add travel notes, research, bookings...", key=f"notes_{dest['place']}")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.button("Mark as Booked", key=f"book_{dest['place']}")
                with col2:
                    st.button("Add to Calendar", key=f"cal_{dest['place']}")
                with col3:
                    st.button("Remove", key=f"remove_{dest['place']}")

# Right panel logic handled after main content