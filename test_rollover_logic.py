#!/usr/bin/env python3
"""
Unit tests for task auto-rollover logic without full app initialization.
Tests core rollover functionality in isolation.
"""

import pytest
import datetime as dt
import tempfile
import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Create isolated models for testing
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
    due_date = Column(Date, nullable=True)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow)
    notes = Column(Text, default="")
    priority = Column(Integer, default=0)
    auto_rollover = Column(Boolean, default=True)
    user = relationship("User")

class TaskRolloverHistory(Base):
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
    __tablename__ = "user_rollover_preferences"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    auto_rollover_enabled = Column(Boolean, default=True)
    rollover_time_hours = Column(Integer, default=6)
    rollover_incomplete_only = Column(Boolean, default=True)
    max_rollover_days = Column(Integer, default=7)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow)
    user = relationship("User")

# Isolated rollover manager for testing
class TestTaskRolloverManager:
    """Test version of TaskRolloverManager"""
    
    @staticmethod
    def get_user_rollover_preference(session, user_id: int) -> UserRolloverPreference:
        """Get or create user rollover preference"""
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
    def should_rollover_task(session, task: Task, user_preference: UserRolloverPreference) -> bool:
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
        rollover_count = session.query(TaskRolloverHistory).filter(
            TaskRolloverHistory.task_id == task.id
        ).count()
        
        if rollover_count >= user_preference.max_rollover_days:
            return False
        
        return True
    
    @staticmethod
    def rollover_task(session, task: Task, target_date: dt.date) -> bool:
        """Roll over a task to the target date"""
        try:
            # Store original date for history
            original_date = task.due_date
            
            # Update task due date
            task.due_date = target_date
            task.updated_at = dt.datetime.utcnow()
            
            # Create rollover history entry
            history_entry = TaskRolloverHistory(
                task_id=task.id,
                user_id=task.user_id,
                original_date=original_date,
                rolled_to_date=target_date
            )
            session.add(history_entry)
            session.commit()
            return True
            
        except Exception as e:
            print(f"Error rolling over task {task.id}: {e}")
            session.rollback()
            return False
    
    @staticmethod
    def process_daily_rollover(session, user_id: int, current_date: dt.date) -> dict:
        """Process daily rollover for a user"""
        results = {
            "processed": 0,
            "rolled_over": 0,
            "skipped": 0,
            "errors": 0
        }
        
        try:
            user_preference = TestTaskRolloverManager.get_user_rollover_preference(session, user_id)
            
            if not user_preference.auto_rollover_enabled:
                return results
            
            # Get incomplete tasks from previous days
            incomplete_tasks = session.query(Task).filter(
                Task.user_id == user_id,
                Task.due_date < current_date,
                Task.completed == False,
                Task.scope == "daily",
                Task.auto_rollover == True
            ).all()
            
            for task in incomplete_tasks:
                results["processed"] += 1
                
                if TestTaskRolloverManager.should_rollover_task(session, task, user_preference):
                    if TestTaskRolloverManager.rollover_task(session, task, current_date):
                        results["rolled_over"] += 1
                    else:
                        results["errors"] += 1
                else:
                    results["skipped"] += 1
                    
        except Exception as e:
            print(f"Error processing daily rollover for user {user_id}: {e}")
            results["errors"] += 1
        
        return results


class TestTaskRolloverSystem:
    """Test suite for task rollover system"""
    
    @pytest.fixture
    def db_session(self):
        """Create a temporary database for testing"""
        # Create temporary database file
        db_fd, db_path = tempfile.mkstemp()
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        
        # Create all tables
        Base.metadata.create_all(engine)
        
        # Create session
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        yield session
        
        # Cleanup
        session.close()
        os.close(db_fd)
        os.unlink(db_path)
    
    @pytest.fixture
    def sample_user(self, db_session):
        """Create a sample user for testing"""
        user = User(name="TestUser")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    
    @pytest.fixture
    def sample_tasks(self, db_session, sample_user):
        """Create sample tasks for testing"""
        yesterday = dt.date.today() - dt.timedelta(days=1)
        today = dt.date.today()
        
        tasks = [
            Task(
                user_id=sample_user.id,
                title="Incomplete task from yesterday",
                scope="daily",
                due_date=yesterday,
                completed=False,
                auto_rollover=True
            ),
            Task(
                user_id=sample_user.id,
                title="Completed task from yesterday",
                scope="daily",
                due_date=yesterday,
                completed=True,
                auto_rollover=True
            ),
            Task(
                user_id=sample_user.id,
                title="No rollover task",
                scope="daily",
                due_date=yesterday,
                completed=False,
                auto_rollover=False
            ),
            Task(
                user_id=sample_user.id,
                title="Today's task",
                scope="daily",
                due_date=today,
                completed=False,
                auto_rollover=True
            )
        ]
        
        db_session.add_all(tasks)
        db_session.commit()
        for task in tasks:
            db_session.refresh(task)
        
        return tasks


class TestUserRolloverPreference(TestTaskRolloverSystem):
    """Test UserRolloverPreference model and management"""
    
    def test_user_rollover_preference_creation(self, db_session, sample_user):
        """Test creating user rollover preference"""
        preference = UserRolloverPreference(
            user_id=sample_user.id,
            auto_rollover_enabled=True,
            rollover_time_hours=8,
            rollover_incomplete_only=True,
            max_rollover_days=5
        )
        db_session.add(preference)
        db_session.commit()
        db_session.refresh(preference)
        
        assert preference.id is not None
        assert preference.user_id == sample_user.id
        assert preference.auto_rollover_enabled is True
        assert preference.rollover_time_hours == 8
        assert preference.rollover_incomplete_only is True
        assert preference.max_rollover_days == 5
        assert preference.created_at is not None
        assert preference.updated_at is not None
    
    def test_user_rollover_preference_defaults(self, db_session, sample_user):
        """Test default values for user rollover preference"""
        preference = UserRolloverPreference(user_id=sample_user.id)
        db_session.add(preference)
        db_session.commit()
        db_session.refresh(preference)
        
        assert preference.auto_rollover_enabled is True  # Default
        assert preference.rollover_time_hours == 6  # Default 6 AM
        assert preference.rollover_incomplete_only is True  # Default
        assert preference.max_rollover_days == 7  # Default 7 days
    
    def test_get_user_rollover_preference_existing(self, db_session, sample_user):
        """Test getting existing user rollover preference"""
        # Create preference
        original_preference = UserRolloverPreference(
            user_id=sample_user.id,
            auto_rollover_enabled=False,
            max_rollover_days=3
        )
        db_session.add(original_preference)
        db_session.commit()
        
        # Get preference
        preference = TestTaskRolloverManager.get_user_rollover_preference(db_session, sample_user.id)
        
        assert preference.user_id == sample_user.id
        assert preference.auto_rollover_enabled is False
        assert preference.max_rollover_days == 3
    
    def test_get_user_rollover_preference_create_new(self, db_session, sample_user):
        """Test creating new user rollover preference when none exists"""
        # Get preference (should create new one)
        preference = TestTaskRolloverManager.get_user_rollover_preference(db_session, sample_user.id)
        
        assert preference.user_id == sample_user.id
        assert preference.auto_rollover_enabled is True  # Default
        assert preference.max_rollover_days == 7  # Default


class TestTaskRolloverLogic(TestTaskRolloverSystem):
    """Test task rollover logic and decision making"""
    
    def test_should_rollover_task_enabled(self, db_session, sample_user, sample_tasks):
        """Test should_rollover_task with enabled preferences"""
        task = sample_tasks[0]  # Incomplete task with auto_rollover=True
        
        preference = UserRolloverPreference(
            user_id=sample_user.id,
            auto_rollover_enabled=True,
            rollover_incomplete_only=True,
            max_rollover_days=7
        )
        
        should_rollover = TestTaskRolloverManager.should_rollover_task(db_session, task, preference)
        assert should_rollover is True
    
    def test_should_rollover_task_disabled_preference(self, db_session, sample_user, sample_tasks):
        """Test should_rollover_task with disabled user preference"""
        task = sample_tasks[0]  # Incomplete task with auto_rollover=True
        
        preference = UserRolloverPreference(
            user_id=sample_user.id,
            auto_rollover_enabled=False,  # Disabled
            rollover_incomplete_only=True,
            max_rollover_days=7
        )
        
        should_rollover = TestTaskRolloverManager.should_rollover_task(db_session, task, preference)
        assert should_rollover is False
    
    def test_should_rollover_task_disabled_task(self, db_session, sample_user, sample_tasks):
        """Test should_rollover_task with task auto_rollover disabled"""
        task = sample_tasks[2]  # Task with auto_rollover=False
        
        preference = UserRolloverPreference(
            user_id=sample_user.id,
            auto_rollover_enabled=True,
            rollover_incomplete_only=True,
            max_rollover_days=7
        )
        
        should_rollover = TestTaskRolloverManager.should_rollover_task(db_session, task, preference)
        assert should_rollover is False
    
    def test_should_rollover_task_completed(self, db_session, sample_user, sample_tasks):
        """Test should_rollover_task with completed task"""
        task = sample_tasks[1]  # Completed task
        
        preference = UserRolloverPreference(
            user_id=sample_user.id,
            auto_rollover_enabled=True,
            rollover_incomplete_only=True,
            max_rollover_days=7
        )
        
        should_rollover = TestTaskRolloverManager.should_rollover_task(db_session, task, preference)
        assert should_rollover is False
    
    def test_should_rollover_task_max_rollovers_exceeded(self, db_session, sample_user, sample_tasks):
        """Test should_rollover_task when max rollovers exceeded"""
        task = sample_tasks[0]  # Incomplete task
        
        # Create multiple rollover history entries to exceed limit
        for i in range(3):
            history = TaskRolloverHistory(
                task_id=task.id,
                user_id=sample_user.id,
                original_date=dt.date.today() - dt.timedelta(days=i+1),
                rolled_to_date=dt.date.today() - dt.timedelta(days=i)
            )
            db_session.add(history)
        db_session.commit()
        
        preference = UserRolloverPreference(
            user_id=sample_user.id,
            auto_rollover_enabled=True,
            rollover_incomplete_only=True,
            max_rollover_days=2  # Lower than number of existing rollovers
        )
        
        should_rollover = TestTaskRolloverManager.should_rollover_task(db_session, task, preference)
        assert should_rollover is False


class TestTaskRolloverExecution(TestTaskRolloverSystem):
    """Test task rollover execution"""
    
    def test_rollover_task_success(self, db_session, sample_user, sample_tasks):
        """Test successful task rollover"""
        task = sample_tasks[0]  # Incomplete task from yesterday
        original_date = task.due_date
        target_date = dt.date.today()
        
        success = TestTaskRolloverManager.rollover_task(db_session, task, target_date)
        
        assert success is True
        
        # Verify task was updated
        db_session.refresh(task)
        assert task.due_date == target_date
        assert task.updated_at is not None
        
        # Verify history was created
        history = db_session.query(TaskRolloverHistory).filter(
            TaskRolloverHistory.task_id == task.id
        ).first()
        
        assert history is not None
        assert history.original_date == original_date
        assert history.rolled_to_date == target_date
        assert history.user_id == sample_user.id


class TestDailyRolloverProcessing(TestTaskRolloverSystem):
    """Test daily rollover processing"""
    
    def test_process_daily_rollover_success(self, db_session, sample_user, sample_tasks):
        """Test successful daily rollover processing"""
        current_date = dt.date.today()
        
        # Create user preference
        preference = UserRolloverPreference(
            user_id=sample_user.id,
            auto_rollover_enabled=True,
            max_rollover_days=7
        )
        db_session.add(preference)
        db_session.commit()
        
        results = TestTaskRolloverManager.process_daily_rollover(db_session, sample_user.id, current_date)
        
        assert "processed" in results
        assert "rolled_over" in results
        assert "skipped" in results
        assert "errors" in results
        
        # Should process incomplete tasks from previous days
        assert results["processed"] >= 1
        assert results["rolled_over"] >= 1
    
    def test_process_daily_rollover_disabled(self, db_session, sample_user, sample_tasks):
        """Test daily rollover processing when disabled"""
        current_date = dt.date.today()
        
        # Create disabled user preference
        preference = UserRolloverPreference(
            user_id=sample_user.id,
            auto_rollover_enabled=False  # Disabled
        )
        db_session.add(preference)
        db_session.commit()
        
        results = TestTaskRolloverManager.process_daily_rollover(db_session, sample_user.id, current_date)
        
        # Should not process any tasks when disabled
        assert results["processed"] == 0
        assert results["rolled_over"] == 0
        assert results["skipped"] == 0
        assert results["errors"] == 0


class TestRolloverEdgeCases(TestTaskRolloverSystem):
    """Test edge cases and error handling"""
    
    def test_rollover_with_future_date_task(self, db_session, sample_user):
        """Test rollover doesn't affect future date tasks"""
        future_date = dt.date.today() + dt.timedelta(days=1)
        
        future_task = Task(
            user_id=sample_user.id,
            title="Future task",
            scope="daily",
            due_date=future_date,
            completed=False,
            auto_rollover=True
        )
        db_session.add(future_task)
        db_session.commit()
        
        # Create user preference
        preference = UserRolloverPreference(
            user_id=sample_user.id,
            auto_rollover_enabled=True
        )
        db_session.add(preference)
        db_session.commit()
        
        results = TestTaskRolloverManager.process_daily_rollover(db_session, sample_user.id, dt.date.today())
        
        # Future task should not be processed
        assert results["processed"] == 0
    
    def test_rollover_with_weekly_scope_task(self, db_session, sample_user):
        """Test rollover only affects daily scope tasks"""
        yesterday = dt.date.today() - dt.timedelta(days=1)
        
        weekly_task = Task(
            user_id=sample_user.id,
            title="Weekly task",
            scope="weekly",  # Not daily
            due_date=yesterday,
            completed=False,
            auto_rollover=True
        )
        db_session.add(weekly_task)
        db_session.commit()
        
        # Create user preference
        preference = UserRolloverPreference(
            user_id=sample_user.id,
            auto_rollover_enabled=True
        )
        db_session.add(preference)
        db_session.commit()
        
        results = TestTaskRolloverManager.process_daily_rollover(db_session, sample_user.id, dt.date.today())
        
        # Weekly task should not be processed
        assert results["processed"] == 0


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])