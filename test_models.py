#!/usr/bin/env python3
"""
Unit tests for enhanced data models in BlueNest application.
Tests VisionBoardItem, DashboardMetric, and enhanced Task model.
"""

import pytest
import datetime as dt
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import models and base from app
from app import Base, User, Task, VisionBoardItem, DashboardMetric, DailyNote


class TestDatabaseModels:
    """Test suite for all database models"""
    
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


class TestUser(TestDatabaseModels):
    """Test User model"""
    
    def test_user_creation(self, db_session):
        """Test basic user creation"""
        user = User(name="Ravi")
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert user.name == "Ravi"
    
    def test_user_unique_constraint(self, db_session):
        """Test that user names must be unique"""
        user1 = User(name="Ravi")
        user2 = User(name="Ravi")
        
        db_session.add(user1)
        db_session.commit()
        
        db_session.add(user2)
        with pytest.raises(Exception):  # Should raise integrity error
            db_session.commit()


class TestEnhancedTask(TestDatabaseModels):
    """Test enhanced Task model with new fields"""
    
    def test_task_creation_with_new_fields(self, db_session, sample_user):
        """Test task creation with new priority, auto_rollover, and updated_at fields"""
        task = Task(
            user_id=sample_user.id,
            title="Test Task",
            scope="daily",
            due_date=dt.date.today(),
            priority=5,
            auto_rollover=False
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        
        assert task.id is not None
        assert task.title == "Test Task"
        assert task.priority == 5
        assert task.auto_rollover is False
        assert task.updated_at is not None
        assert isinstance(task.updated_at, dt.datetime)
    
    def test_task_default_values(self, db_session, sample_user):
        """Test that new fields have correct default values"""
        task = Task(
            user_id=sample_user.id,
            title="Default Task",
            scope="daily"
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        
        assert task.priority == 0  # Default priority
        assert task.auto_rollover is True  # Default auto_rollover
        assert task.updated_at is not None
        assert task.created_at is not None
    
    def test_task_user_relationship(self, db_session, sample_user):
        """Test that task properly relates to user"""
        task = Task(
            user_id=sample_user.id,
            title="Relationship Test",
            scope="daily"
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        
        assert task.user.name == sample_user.name
        assert task.user.id == sample_user.id


class TestVisionBoardItem(TestDatabaseModels):
    """Test VisionBoardItem model"""
    
    def test_vision_board_item_creation(self, db_session, sample_user):
        """Test basic vision board item creation"""
        item = VisionBoardItem(
            user_id=sample_user.id,
            title="My Goal",
            content_type="text",
            content_data="This is my vision for the future",
            position_x=100,
            position_y=200,
            width=300,
            height=250
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        
        assert item.id is not None
        assert item.title == "My Goal"
        assert item.content_type == "text"
        assert item.content_data == "This is my vision for the future"
        assert item.position_x == 100
        assert item.position_y == 200
        assert item.width == 300
        assert item.height == 250
        assert item.created_at is not None
        assert item.updated_at is not None
    
    def test_vision_board_item_default_values(self, db_session, sample_user):
        """Test default values for vision board item"""
        item = VisionBoardItem(
            user_id=sample_user.id,
            content_type="image",
            content_data="/path/to/image.jpg"
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        
        assert item.position_x == 0  # Default position
        assert item.position_y == 0  # Default position
        assert item.width == 200  # Default width
        assert item.height == 150  # Default height
        assert item.title is None  # Optional title
    
    def test_vision_board_item_content_types(self, db_session, sample_user):
        """Test different content types for vision board items"""
        content_types = ["text", "image", "video", "link"]
        
        for content_type in content_types:
            item = VisionBoardItem(
                user_id=sample_user.id,
                content_type=content_type,
                content_data=f"sample_{content_type}_data"
            )
            db_session.add(item)
        
        db_session.commit()
        
        # Verify all items were created
        items = db_session.query(VisionBoardItem).filter(
            VisionBoardItem.user_id == sample_user.id
        ).all()
        
        assert len(items) == 4
        stored_types = [item.content_type for item in items]
        assert set(stored_types) == set(content_types)
    
    def test_vision_board_item_user_relationship(self, db_session, sample_user):
        """Test vision board item user relationship"""
        item = VisionBoardItem(
            user_id=sample_user.id,
            content_type="text",
            content_data="Test content"
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        
        assert item.user.name == sample_user.name
        assert item.user.id == sample_user.id


class TestDashboardMetric(TestDatabaseModels):
    """Test DashboardMetric model"""
    
    def test_dashboard_metric_creation(self, db_session, sample_user):
        """Test basic dashboard metric creation"""
        metric = DashboardMetric(
            user_id=sample_user.id,
            metric_type="completion_rate",
            metric_value="85%",
            date_recorded=dt.date(2025, 1, 15)
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)
        
        assert metric.id is not None
        assert metric.metric_type == "completion_rate"
        assert metric.metric_value == "85%"
        assert metric.date_recorded == dt.date(2025, 1, 15)
        assert metric.created_at is not None
    
    def test_dashboard_metric_default_date(self, db_session, sample_user):
        """Test that dashboard metric uses today as default date"""
        metric = DashboardMetric(
            user_id=sample_user.id,
            metric_type="streak",
            metric_value="7 days"
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)
        
        assert metric.date_recorded == dt.date.today()
    
    def test_dashboard_metric_types(self, db_session, sample_user):
        """Test different metric types"""
        metric_types = ["goal", "completion_rate", "streak"]
        
        for i, metric_type in enumerate(metric_types):
            metric = DashboardMetric(
                user_id=sample_user.id,
                metric_type=metric_type,
                metric_value=f"value_{i}"
            )
            db_session.add(metric)
        
        db_session.commit()
        
        # Verify all metrics were created
        metrics = db_session.query(DashboardMetric).filter(
            DashboardMetric.user_id == sample_user.id
        ).all()
        
        assert len(metrics) == 3
        stored_types = [metric.metric_type for metric in metrics]
        assert set(stored_types) == set(metric_types)
    
    def test_dashboard_metric_user_relationship(self, db_session, sample_user):
        """Test dashboard metric user relationship"""
        metric = DashboardMetric(
            user_id=sample_user.id,
            metric_type="goal",
            metric_value="Complete 10 tasks"
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)
        
        assert metric.user.name == sample_user.name
        assert metric.user.id == sample_user.id


class TestModelIntegration(TestDatabaseModels):
    """Test integration between different models"""
    
    def test_user_with_all_related_models(self, db_session, sample_user):
        """Test that a user can have all types of related records"""
        # Create a task
        task = Task(
            user_id=sample_user.id,
            title="Integration Test Task",
            scope="daily",
            priority=3
        )
        
        # Create a vision board item
        vision_item = VisionBoardItem(
            user_id=sample_user.id,
            content_type="text",
            content_data="Integration test vision"
        )
        
        # Create a dashboard metric
        metric = DashboardMetric(
            user_id=sample_user.id,
            metric_type="completion_rate",
            metric_value="90%"
        )
        
        # Create a daily note
        note = DailyNote(
            user_id=sample_user.id,
            date=dt.date.today(),
            content_json='{"ops":[{"insert":"Integration test note\\n"}]}'
        )
        
        db_session.add_all([task, vision_item, metric, note])
        db_session.commit()
        
        # Verify all records exist and relate to the same user
        user_tasks = db_session.query(Task).filter(Task.user_id == sample_user.id).all()
        user_vision_items = db_session.query(VisionBoardItem).filter(
            VisionBoardItem.user_id == sample_user.id
        ).all()
        user_metrics = db_session.query(DashboardMetric).filter(
            DashboardMetric.user_id == sample_user.id
        ).all()
        user_notes = db_session.query(DailyNote).filter(
            DailyNote.user_id == sample_user.id
        ).all()
        
        assert len(user_tasks) == 1
        assert len(user_vision_items) == 1
        assert len(user_metrics) == 1
        assert len(user_notes) == 1
        
        # Verify relationships work
        assert user_tasks[0].user.name == sample_user.name
        assert user_vision_items[0].user.name == sample_user.name
        assert user_metrics[0].user.name == sample_user.name
        assert user_notes[0].user.name == sample_user.name


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])