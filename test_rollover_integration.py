#!/usr/bin/env python3
"""
Integration tests for task auto-rollover system.
Tests the complete rollover workflow including TodoInterface integration.
"""

import pytest
import datetime as dt
import tempfile
import os
from unittest.mock import patch, Mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import from app
from app import (
    Base, User, Task, TaskRolloverHistory, UserRolloverPreference,
    TaskRolloverManager, TodoInterface
)


class TestRolloverIntegration:
    """Integration tests for rollover system"""
    
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
    
    def test_rollover_integration_workflow(self, db_session, sample_user):
        """Test complete rollover workflow"""
        yesterday = dt.date.today() - dt.timedelta(days=1)
        today = dt.date.today()
        
        # Create incomplete task from yesterday
        incomplete_task = Task(
            user_id=sample_user.id,
            title="Incomplete task from yesterday",
            scope="daily",
            due_date=yesterday,
            completed=False,
            auto_rollover=True
        )
        db_session.add(incomplete_task)
        db_session.commit()
        db_session.refresh(incomplete_task)
        
        # Create user preference
        preference = UserRolloverPreference(
            user_id=sample_user.id,
            auto_rollover_enabled=True,
            max_rollover_days=7
        )
        db_session.add(preference)
        db_session.commit()
        
        # Mock SessionLocal to use our test session
        with patch('app.SessionLocal') as mock_session_local:
            mock_session_local.return_value.__enter__.return_value = db_session
            
            # Process rollover
            results = TaskRolloverManager.process_daily_rollover(sample_user.id, today)
            
            # Verify rollover occurred
            assert results["processed"] == 1
            assert results["rolled_over"] == 1
            assert results["skipped"] == 0
            assert results["errors"] == 0
            
            # Verify task was moved to today
            db_session.refresh(incomplete_task)
            assert incomplete_task.due_date == today
            
            # Verify history was created
            history = db_session.query(TaskRolloverHistory).filter(
                TaskRolloverHistory.task_id == incomplete_task.id
            ).first()
            assert history is not None
            assert history.original_date == yesterday
            assert history.rolled_to_date == today
    
    def test_todo_interface_rollover_trigger(self, db_session, sample_user):
        """Test that TodoInterface triggers rollover check"""
        yesterday = dt.date.today() - dt.timedelta(days=1)
        today = dt.date.today()
        
        # Create incomplete task from yesterday
        incomplete_task = Task(
            user_id=sample_user.id,
            title="Task to be rolled over",
            scope="daily",
            due_date=yesterday,
            completed=False,
            auto_rollover=True
        )
        db_session.add(incomplete_task)
        db_session.commit()
        
        # Create user preference
        preference = UserRolloverPreference(
            user_id=sample_user.id,
            auto_rollover_enabled=True,
            max_rollover_days=7
        )
        db_session.add(preference)
        db_session.commit()
        
        # Mock SessionLocal and streamlit components
        with patch('app.SessionLocal') as mock_session_local, \
             patch('app.st') as mock_st:
            
            mock_session_local.return_value.__enter__.return_value = db_session
            mock_st.session_state = {}
            
            # Create TodoInterface for today (should trigger rollover)
            todo_interface = TodoInterface(sample_user.id, today)
            
            # Verify rollover was triggered by checking task date
            db_session.refresh(incomplete_task)
            assert incomplete_task.due_date == today
    
    def test_rollover_insights_integration(self, db_session, sample_user):
        """Test rollover insights functionality"""
        yesterday = dt.date.today() - dt.timedelta(days=1)
        today = dt.date.today()
        
        # Create task and rollover history
        task = Task(
            user_id=sample_user.id,
            title="Test task",
            scope="daily",
            due_date=today,
            completed=False,
            auto_rollover=True
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        
        # Create rollover history
        history = TaskRolloverHistory(
            task_id=task.id,
            user_id=sample_user.id,
            original_date=yesterday,
            rolled_to_date=today
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
        
        # Mock SessionLocal
        with patch('app.SessionLocal') as mock_session_local:
            mock_session_local.return_value.__enter__.return_value = db_session
            
            # Get insights
            insights = TaskRolloverManager.get_rollover_insights(sample_user.id)
            
            assert insights["total_rollovers_30_days"] == 1
            assert insights["rollover_enabled"] is True
            assert "frequent_rollovers" in insights
    
    def test_rollover_with_multiple_users(self, db_session):
        """Test rollover works correctly with multiple users"""
        yesterday = dt.date.today() - dt.timedelta(days=1)
        today = dt.date.today()
        
        # Create two users
        user1 = User(name="User1")
        user2 = User(name="User2")
        db_session.add_all([user1, user2])
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)
        
        # Create tasks for each user
        task1 = Task(
            user_id=user1.id,
            title="User1 task",
            scope="daily",
            due_date=yesterday,
            completed=False,
            auto_rollover=True
        )
        task2 = Task(
            user_id=user2.id,
            title="User2 task",
            scope="daily",
            due_date=yesterday,
            completed=False,
            auto_rollover=True
        )
        db_session.add_all([task1, task2])
        db_session.commit()
        
        # Create preferences for each user
        pref1 = UserRolloverPreference(user_id=user1.id, auto_rollover_enabled=True)
        pref2 = UserRolloverPreference(user_id=user2.id, auto_rollover_enabled=False)  # Disabled
        db_session.add_all([pref1, pref2])
        db_session.commit()
        
        # Mock SessionLocal
        with patch('app.SessionLocal') as mock_session_local:
            mock_session_local.return_value.__enter__.return_value = db_session
            
            # Process rollover for user1 (enabled)
            results1 = TaskRolloverManager.process_daily_rollover(user1.id, today)
            assert results1["rolled_over"] == 1
            
            # Process rollover for user2 (disabled)
            results2 = TaskRolloverManager.process_daily_rollover(user2.id, today)
            assert results2["rolled_over"] == 0
            
            # Verify tasks
            db_session.refresh(task1)
            db_session.refresh(task2)
            
            assert task1.due_date == today  # Rolled over
            assert task2.due_date == yesterday  # Not rolled over
    
    def test_rollover_preference_management(self, db_session, sample_user):
        """Test rollover preference creation and management"""
        with patch('app.SessionLocal') as mock_session_local:
            mock_session_local.return_value.__enter__.return_value = db_session
            
            # Get preference (should create new one)
            preference = TaskRolloverManager.get_user_rollover_preference(sample_user.id)
            
            assert preference.user_id == sample_user.id
            assert preference.auto_rollover_enabled is True  # Default
            assert preference.max_rollover_days == 7  # Default
            
            # Verify it was saved to database
            saved_preference = db_session.query(UserRolloverPreference).filter(
                UserRolloverPreference.user_id == sample_user.id
            ).first()
            
            assert saved_preference is not None
            assert saved_preference.id == preference.id
    
    def test_rollover_history_tracking(self, db_session, sample_user):
        """Test rollover history tracking and retrieval"""
        yesterday = dt.date.today() - dt.timedelta(days=1)
        today = dt.date.today()
        
        # Create task
        task = Task(
            user_id=sample_user.id,
            title="History test task",
            scope="daily",
            due_date=yesterday,
            completed=False,
            auto_rollover=True
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        
        # Mock SessionLocal
        with patch('app.SessionLocal') as mock_session_local:
            mock_session_local.return_value.__enter__.return_value = db_session
            
            # Perform rollover
            success = TaskRolloverManager.rollover_task(task, today)
            assert success is True
            
            # Get rollover history
            history = TaskRolloverManager.get_rollover_history(sample_user.id, days=30)
            
            assert len(history) == 1
            assert history[0].task_id == task.id
            assert history[0].original_date == yesterday
            assert history[0].rolled_to_date == today
    
    def test_rollover_max_limit_enforcement(self, db_session, sample_user):
        """Test that max rollover limit is enforced"""
        yesterday = dt.date.today() - dt.timedelta(days=1)
        today = dt.date.today()
        
        # Create task
        task = Task(
            user_id=sample_user.id,
            title="Max limit test task",
            scope="daily",
            due_date=yesterday,
            completed=False,
            auto_rollover=True
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        
        # Create preference with low max rollover limit
        preference = UserRolloverPreference(
            user_id=sample_user.id,
            auto_rollover_enabled=True,
            max_rollover_days=2
        )
        db_session.add(preference)
        db_session.commit()
        
        # Create multiple rollover history entries to exceed limit
        for i in range(3):
            history = TaskRolloverHistory(
                task_id=task.id,
                user_id=sample_user.id,
                original_date=dt.date.today() - dt.timedelta(days=i+2),
                rolled_to_date=dt.date.today() - dt.timedelta(days=i+1)
            )
            db_session.add(history)
        db_session.commit()
        
        # Mock SessionLocal
        with patch('app.SessionLocal') as mock_session_local:
            mock_session_local.return_value.__enter__.return_value = db_session
            
            # Try to process rollover (should be skipped due to limit)
            results = TaskRolloverManager.process_daily_rollover(sample_user.id, today)
            
            assert results["processed"] == 1
            assert results["rolled_over"] == 0  # Should be 0 due to limit
            assert results["skipped"] == 1


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])