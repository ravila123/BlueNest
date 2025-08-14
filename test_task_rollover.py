#!/usr/bin/env python3
"""
Unit tests for task auto-rollover system in BlueNest application.
Tests rollover logic, user preferences, history tracking, and edge cases.
"""

import pytest
import datetime as dt
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import models and rollover classes from app
from app import (
    Base, User, Task, TaskRolloverHistory, UserRolloverPreference,
    TaskRolloverManager, trigger_daily_rollover_check
)


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
        
        # Mock SessionLocal to use our test session
        with pytest.MonkeyPatch().context() as m:
            def mock_session_local():
                return db_session
            m.setattr("app.SessionLocal", mock_session_local)
            
            # Get preference
            preference = TaskRolloverManager.get_user_rollover_preference(sample_user.id)
            
            assert preference.user_id == sample_user.id
            assert preference.auto_rollover_enabled is False
            assert preference.max_rollover_days == 3
    
    def test_get_user_rollover_preference_create_new(self, db_session, sample_user):
        """Test creating new user rollover preference when none exists"""
        with pytest.MonkeyPatch().context() as m:
            def mock_session_local():
                return db_session
            m.setattr("app.SessionLocal", mock_session_local)
            
            # Get preference (should create new one)
            preference = TaskRolloverManager.get_user_rollover_preference(sample_user.id)
            
            assert preference.user_id == sample_user.id
            assert preference.auto_rollover_enabled is True  # Default
            assert preference.max_rollover_days == 7  # Default


class TestTaskRolloverHistory(TestTaskRolloverSystem):
    """Test TaskRolloverHistory model"""
    
    def test_task_rollover_history_creation(self, db_session, sample_user, sample_tasks):
        """Test creating task rollover history entry"""
        task = sample_tasks[0]  # First task
        original_date = dt.date(2024, 1, 10)
        rolled_to_date = dt.date(2024, 1, 11)
        
        history = TaskRolloverHistory(
            task_id=task.id,
            user_id=sample_user.id,
            original_date=original_date,
            rolled_to_date=rolled_to_date
        )
        db_session.add(history)
        db_session.commit()
        db_session.refresh(history)
        
        assert history.id is not None
        assert history.task_id == task.id
        assert history.user_id == sample_user.id
        assert history.original_date == original_date
        assert history.rolled_to_date == rolled_to_date
        assert history.rollover_timestamp is not None
    
    def test_task_rollover_history_relationships(self, db_session, sample_user, sample_tasks):
        """Test task rollover history relationships"""
        task = sample_tasks[0]
        
        history = TaskRolloverHistory(
            task_id=task.id,
            user_id=sample_user.id,
            original_date=dt.date(2024, 1, 10),
            rolled_to_date=dt.date(2024, 1, 11)
        )
        db_session.add(history)
        db_session.commit()
        db_session.refresh(history)
        
        # Test relationships
        assert history.task.id == task.id
        assert history.task.title == task.title
        assert history.user.id == sample_user.id
        assert history.user.name == sample_user.name


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
        
        should_rollover = TaskRolloverManager.should_rollover_task(task, preference)
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
        
        should_rollover = TaskRolloverManager.should_rollover_task(task, preference)
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
        
        should_rollover = TaskRolloverManager.should_rollover_task(task, preference)
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
        
        should_rollover = TaskRolloverManager.should_rollover_task(task, preference)
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
        
        with pytest.MonkeyPatch().context() as m:
            def mock_session_local():
                return db_session
            m.setattr("app.SessionLocal", mock_session_local)
            
            should_rollover = TaskRolloverManager.should_rollover_task(task, preference)
            assert should_rollover is False


class TestTaskRolloverExecution(TestTaskRolloverSystem):
    """Test task rollover execution"""
    
    def test_rollover_task_success(self, db_session, sample_user, sample_tasks):
        """Test successful task rollover"""
        task = sample_tasks[0]  # Incomplete task from yesterday
        original_date = task.due_date
        target_date = dt.date.today()
        
        with pytest.MonkeyPatch().context() as m:
            def mock_session_local():
                return db_session
            m.setattr("app.SessionLocal", mock_session_local)
            
            success = TaskRolloverManager.rollover_task(task, target_date)
            
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
    
    def test_rollover_task_nonexistent(self, db_session):
        """Test rollover with nonexistent task"""
        with pytest.MonkeyPatch().context() as m:
            def mock_session_local():
                return db_session
            m.setattr("app.SessionLocal", mock_session_local)
            
            # Create a mock task with non-existent ID
            class MockTask:
                id = 99999
            
            mock_task = MockTask()
            success = TaskRolloverManager.rollover_task(mock_task, dt.date.today())
            
            assert success is False


class TestDailyRolloverProcessing(TestTaskRolloverSystem):
    """Test daily rollover processing"""
    
    def test_process_daily_rollover_success(self, db_session, sample_user, sample_tasks):
        """Test successful daily rollover processing"""
        current_date = dt.date.today()
        
        with pytest.MonkeyPatch().context() as m:
            def mock_session_local():
                return db_session
            m.setattr("app.SessionLocal", mock_session_local)
            
            # Create user preference
            preference = UserRolloverPreference(
                user_id=sample_user.id,
                auto_rollover_enabled=True,
                max_rollover_days=7
            )
            db_session.add(preference)
            db_session.commit()
            
            results = TaskRolloverManager.process_daily_rollover(sample_user.id, current_date)
            
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
        
        with pytest.MonkeyPatch().context() as m:
            def mock_session_local():
                return db_session
            m.setattr("app.SessionLocal", mock_session_local)
            
            # Create disabled user preference
            preference = UserRolloverPreference(
                user_id=sample_user.id,
                auto_rollover_enabled=False  # Disabled
            )
            db_session.add(preference)
            db_session.commit()
            
            results = TaskRolloverManager.process_daily_rollover(sample_user.id, current_date)
            
            # Should not process any tasks when disabled
            assert results["processed"] == 0
            assert results["rolled_over"] == 0
            assert results["skipped"] == 0
            assert results["errors"] == 0


class TestRolloverHistory(TestTaskRolloverSystem):
    """Test rollover history and insights"""
    
    def test_get_rollover_history(self, db_session, sample_user, sample_tasks):
        """Test getting rollover history"""
        task = sample_tasks[0]
        
        # Create some history entries
        history_entries = []
        for i in range(5):
            history = TaskRolloverHistory(
                task_id=task.id,
                user_id=sample_user.id,
                original_date=dt.date.today() - dt.timedelta(days=i+2),
                rolled_to_date=dt.date.today() - dt.timedelta(days=i+1),
                rollover_timestamp=dt.datetime.now() - dt.timedelta(days=i)
            )
            history_entries.append(history)
        
        db_session.add_all(history_entries)
        db_session.commit()
        
        with pytest.MonkeyPatch().context() as m:
            def mock_session_local():
                return db_session
            m.setattr("app.SessionLocal", mock_session_local)
            
            history = TaskRolloverManager.get_rollover_history(sample_user.id, days=30)
            
            assert len(history) == 5
            # Should be ordered by timestamp descending
            assert history[0].rollover_timestamp >= history[1].rollover_timestamp
    
    def test_get_rollover_insights(self, db_session, sample_user, sample_tasks):
        """Test getting rollover insights"""
        task = sample_tasks[0]
        
        # Create some recent history entries
        for i in range(3):
            history = TaskRolloverHistory(
                task_id=task.id,
                user_id=sample_user.id,
                original_date=dt.date.today() - dt.timedelta(days=i+1),
                rolled_to_date=dt.date.today() - dt.timedelta(days=i),
                rollover_timestamp=dt.datetime.now() - dt.timedelta(days=i)
            )
            db_session.add(history)
        db_session.commit()
        
        # Create user preference
        preference = UserRolloverPreference(
            user_id=sample_user.id,
            auto_rollover_enabled=True
        )
        db_session.add(preference)
        db_session.commit()
        
        with pytest.MonkeyPatch().context() as m:
            def mock_session_local():
                return db_session
            m.setattr("app.SessionLocal", mock_session_local)
            
            insights = TaskRolloverManager.get_rollover_insights(sample_user.id)
            
            assert "total_rollovers_30_days" in insights
            assert "frequent_rollovers" in insights
            assert "rollover_enabled" in insights
            
            assert insights["total_rollovers_30_days"] == 3
            assert insights["rollover_enabled"] is True


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
        
        with pytest.MonkeyPatch().context() as m:
            def mock_session_local():
                return db_session
            m.setattr("app.SessionLocal", mock_session_local)
            
            # Create user preference
            preference = UserRolloverPreference(
                user_id=sample_user.id,
                auto_rollover_enabled=True
            )
            db_session.add(preference)
            db_session.commit()
            
            results = TaskRolloverManager.process_daily_rollover(sample_user.id, dt.date.today())
            
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
        
        with pytest.MonkeyPatch().context() as m:
            def mock_session_local():
                return db_session
            m.setattr("app.SessionLocal", mock_session_local)
            
            # Create user preference
            preference = UserRolloverPreference(
                user_id=sample_user.id,
                auto_rollover_enabled=True
            )
            db_session.add(preference)
            db_session.commit()
            
            results = TaskRolloverManager.process_daily_rollover(sample_user.id, dt.date.today())
            
            # Weekly task should not be processed
            assert results["processed"] == 0
    
    def test_trigger_daily_rollover_check_multiple_users(self, db_session):
        """Test triggering rollover check for multiple users"""
        # Create multiple users
        users = []
        for i in range(3):
            user = User(name=f"User{i}")
            db_session.add(user)
            users.append(user)
        db_session.commit()
        
        # Create tasks for each user
        yesterday = dt.date.today() - dt.timedelta(days=1)
        for user in users:
            task = Task(
                user_id=user.id,
                title=f"Task for {user.name}",
                scope="daily",
                due_date=yesterday,
                completed=False,
                auto_rollover=True
            )
            db_session.add(task)
        db_session.commit()
        
        with pytest.MonkeyPatch().context() as m:
            def mock_session_local():
                return db_session
            m.setattr("app.SessionLocal", mock_session_local)
            
            results = trigger_daily_rollover_check()
            
            assert isinstance(results, dict)
            assert len(results) == 3  # One result per user
            
            for user in users:
                assert user.name in results
                user_results = results[user.name]
                assert "processed" in user_results
                assert "rolled_over" in user_results


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])