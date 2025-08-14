#!/usr/bin/env python3
"""
Unit tests for Microsoft Teams-style TodoInterface with instant save functionality.
Tests task creation flow, auto-save functionality, and click-to-edit features.
"""

import pytest
import datetime as dt
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import models and TodoInterface from app
from app import Base, User, Task, TodoInterface


class TestTodoInterface:
    """Test suite for TodoInterface class"""
    
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
    def todo_interface(self, sample_user):
        """Create TodoInterface instance for testing"""
        test_date = dt.date(2024, 1, 15)
        return TodoInterface(sample_user.id, test_date)
    
    @pytest.fixture
    def mock_streamlit(self):
        """Mock streamlit components"""
        with patch('app.st') as mock_st:
            mock_st.session_state = {}
            mock_st.markdown = Mock()
            mock_st.text_input = Mock()
            mock_st.caption = Mock()
            mock_st.checkbox = Mock()
            mock_st.button = Mock()
            mock_st.columns = Mock(return_value=[Mock(), Mock(), Mock()])
            mock_st.rerun = Mock()
            yield mock_st


class TestTodoInterfaceInitialization(TestTodoInterface):
    """Test TodoInterface initialization"""
    
    def test_initialization(self, sample_user):
        """Test TodoInterface initializes with correct user_id and date"""
        test_date = dt.date(2024, 1, 15)
        todo_interface = TodoInterface(sample_user.id, test_date)
        
        assert todo_interface.user_id == sample_user.id
        assert todo_interface.date == test_date
    
    def test_initialization_with_different_dates(self, sample_user):
        """Test TodoInterface works with different dates"""
        dates = [
            dt.date(2024, 1, 1),
            dt.date(2024, 6, 15),
            dt.date(2024, 12, 31)
        ]
        
        for test_date in dates:
            todo_interface = TodoInterface(sample_user.id, test_date)
            assert todo_interface.date == test_date


class TestTaskCreation(TestTodoInterface):
    """Test task creation functionality"""
    
    @patch('app.SessionLocal')
    def test_save_task(self, mock_session_local, todo_interface):
        """Test _save_task method creates task in database"""
        # Setup mock session
        mock_session = Mock()
        mock_session_local.return_value.__enter__.return_value = mock_session
        
        # Test task creation
        test_title = "Test Task"
        todo_interface._save_task(test_title)
        
        # Verify task was added to session
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        
        # Verify task properties
        added_task = mock_session.add.call_args[0][0]
        assert isinstance(added_task, Task)
        assert added_task.user_id == todo_interface.user_id
        assert added_task.title == test_title
        assert added_task.scope == "daily"
        assert added_task.due_date == todo_interface.date
    
    def test_save_task_integration(self, todo_interface, db_session, sample_user):
        """Test _save_task integration with real database"""
        # Patch SessionLocal to use our test session
        with patch('app.SessionLocal') as mock_session_local:
            mock_session_local.return_value.__enter__.return_value = db_session
            
            test_title = "Integration Test Task"
            todo_interface._save_task(test_title)
            
            # Verify task was saved to database
            saved_task = db_session.query(Task).filter(
                Task.user_id == sample_user.id,
                Task.title == test_title
            ).first()
            
            assert saved_task is not None
            assert saved_task.title == test_title
            assert saved_task.scope == "daily"
            assert saved_task.due_date == todo_interface.date
    
    @patch('app.st')
    def test_render_task_input(self, mock_st, todo_interface):
        """Test render_task_input creates proper input field"""
        mock_st.session_state = {}
        
        todo_interface.render_task_input()
        
        # Verify markdown wrapper is created
        mock_st.markdown.assert_any_call("<div class='todo-input'>", unsafe_allow_html=True)
        mock_st.markdown.assert_any_call("</div>", unsafe_allow_html=True)
        
        # Verify text input is created
        mock_st.text_input.assert_called_once()
        call_args = mock_st.text_input.call_args
        
        assert call_args[0][0] == "Add a task"  # Label
        assert "placeholder" in call_args[1]
        assert call_args[1]["placeholder"] == "Type and press Enter…"
        assert call_args[1]["label_visibility"] == "collapsed"
        assert "on_change" in call_args[1]
    
    @patch('app.st')
    def test_task_creation_flow(self, mock_st, todo_interface):
        """Test complete task creation flow with input handling"""
        # Setup mock session state with task input
        test_title = "New Task from Input"
        input_key = f"new_task_{todo_interface.user_id}_{todo_interface.date}"
        mock_st.session_state = {input_key: test_title}
        
        with patch.object(todo_interface, '_save_task') as mock_save:
            todo_interface.render_task_input()
            
            # Get the on_change handler
            on_change_handler = mock_st.text_input.call_args[1]["on_change"]
            
            # Simulate Enter key press (on_change trigger)
            on_change_handler()
            
            # Verify task was saved
            mock_save.assert_called_once_with(test_title)
            
            # Verify input was cleared
            assert mock_st.session_state[input_key] == ""
            
            # Verify rerun was called
            mock_st.rerun.assert_called_once()
    
    @patch('app.st')
    def test_empty_input_handling(self, mock_st, todo_interface):
        """Test that empty or whitespace-only input is ignored"""
        empty_inputs = ["", "   ", "\t", "\n", "  \t  \n  "]
        
        for empty_input in empty_inputs:
            mock_st.session_state = {
                f"new_task_{todo_interface.user_id}_{todo_interface.date}": empty_input
            }
            
            with patch.object(todo_interface, '_save_task') as mock_save:
                todo_interface.render_task_input()
                
                # Get and trigger the on_change handler
                on_change_handler = mock_st.text_input.call_args[1]["on_change"]
                on_change_handler()
                
                # Verify task was not saved for empty input
                mock_save.assert_not_called()


class TestTaskListRendering(TestTodoInterface):
    """Test task list rendering functionality"""
    
    @patch('app.SessionLocal')
    @patch('app.st')
    def test_render_task_list_empty(self, mock_st, mock_session_local, todo_interface):
        """Test rendering empty task list"""
        # Setup mock session with no tasks
        mock_session = Mock()
        mock_session_local.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        todo_interface.render_task_list()
        
        # Verify empty state message is shown
        mock_st.caption.assert_called_once_with("No tasks yet — add one above")
    
    @patch('app.SessionLocal')
    @patch('app.st')
    def test_render_task_list_with_tasks(self, mock_st, mock_session_local, todo_interface, sample_user):
        """Test rendering task list with tasks"""
        # Create mock tasks
        mock_task1 = Mock()
        mock_task1.id = 1
        mock_task1.title = "Task 1"
        mock_task1.completed = False
        
        mock_task2 = Mock()
        mock_task2.id = 2
        mock_task2.title = "Task 2"
        mock_task2.completed = True
        
        # Setup mock session
        mock_session = Mock()
        mock_session_local.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_task1, mock_task2]
        
        # Mock streamlit columns
        mock_col1, mock_col2, mock_col3 = Mock(), Mock(), Mock()
        mock_st.columns.return_value = [mock_col1, mock_col2, mock_col3]
        mock_st.session_state = {}
        
        with patch.object(todo_interface, '_render_task_item') as mock_render_item:
            todo_interface.render_task_list()
            
            # Verify _render_task_item was called for each task
            assert mock_render_item.call_count == 2
            mock_render_item.assert_any_call(mock_task1)
            mock_render_item.assert_any_call(mock_task2)
    
    def test_task_list_query_parameters(self, todo_interface):
        """Test that task list query uses correct parameters"""
        with patch('app.SessionLocal') as mock_session_local:
            mock_session = Mock()
            mock_session_local.return_value.__enter__.return_value = mock_session
            
            # Setup query chain
            mock_query = mock_session.query.return_value
            mock_filter = mock_query.filter.return_value
            mock_order = mock_filter.order_by.return_value
            mock_order.all.return_value = []
            
            todo_interface.render_task_list()
            
            # Verify query was called with Task model
            mock_session.query.assert_called_once_with(Task)
            
            # Verify filter was called (we can't easily test the exact filter conditions
            # due to SQLAlchemy's complex filter syntax, but we can verify it was called)
            mock_query.filter.assert_called_once()
            mock_filter.order_by.assert_called_once()


class TestTaskItemRendering(TestTodoInterface):
    """Test individual task item rendering"""
    
    @patch('app.st')
    def test_render_task_item_display_mode(self, mock_st, todo_interface):
        """Test rendering task item in display mode"""
        # Create mock task
        mock_task = Mock()
        mock_task.id = 1
        mock_task.title = "Test Task"
        mock_task.completed = False
        
        # Setup mock streamlit columns with context manager support
        mock_col1 = Mock()
        mock_col1.__enter__ = Mock(return_value=mock_col1)
        mock_col1.__exit__ = Mock(return_value=None)
        
        mock_col2 = Mock()
        mock_col2.__enter__ = Mock(return_value=mock_col2)
        mock_col2.__exit__ = Mock(return_value=None)
        
        mock_col3 = Mock()
        mock_col3.__enter__ = Mock(return_value=mock_col3)
        mock_col3.__exit__ = Mock(return_value=None)
        
        mock_st.columns.return_value = [mock_col1, mock_col2, mock_col3]
        mock_st.session_state = {}
        
        # Mock checkbox to return the same value as task.completed to avoid database operations
        mock_st.checkbox.return_value = mock_task.completed
        
        # Mock button to return False to avoid triggering actions
        mock_st.button.return_value = False
        
        todo_interface._render_task_item(mock_task)
        
        # Verify HTML wrapper
        mock_st.markdown.assert_any_call("<div class='todo-item'>", unsafe_allow_html=True)
        mock_st.markdown.assert_any_call("</div>", unsafe_allow_html=True)
        
        # Verify columns were created
        mock_st.columns.assert_called_once_with([0.08, 0.76, 0.16])
        
        # Verify checkbox was created
        mock_st.checkbox.assert_called_once()
        
        # Verify task title button was created
        mock_st.button.assert_called()
    
    @patch('app.st')
    def test_render_task_item_edit_mode(self, mock_st, todo_interface):
        """Test rendering task item in edit mode"""
        # Create mock task
        mock_task = Mock()
        mock_task.id = 1
        mock_task.title = "Test Task"
        mock_task.completed = False
        
        # Setup edit mode in session state
        edit_key = f"edit_{mock_task.id}"
        mock_st.session_state = {edit_key: True}
        
        # Setup mock streamlit columns with context manager support
        mock_col1 = Mock()
        mock_col1.__enter__ = Mock(return_value=mock_col1)
        mock_col1.__exit__ = Mock(return_value=None)
        
        mock_col2 = Mock()
        mock_col2.__enter__ = Mock(return_value=mock_col2)
        mock_col2.__exit__ = Mock(return_value=None)
        
        mock_col3 = Mock()
        mock_col3.__enter__ = Mock(return_value=mock_col3)
        mock_col3.__exit__ = Mock(return_value=None)
        
        mock_st.columns.return_value = [mock_col1, mock_col2, mock_col3]
        
        # Mock checkbox to return the same value as task.completed to avoid database operations
        mock_st.checkbox.return_value = mock_task.completed
        
        # Mock button to return False to avoid triggering actions
        mock_st.button.return_value = False
        
        todo_interface._render_task_item(mock_task)
        
        # Verify text input for editing was created
        mock_st.text_input.assert_called()
        text_input_call = mock_st.text_input.call_args
        assert text_input_call[1]["value"] == mock_task.title
        assert text_input_call[1]["label_visibility"] == "collapsed"


class TestTaskOperations(TestTodoInterface):
    """Test task operations (toggle, update, delete)"""
    
    @patch('app.SessionLocal')
    def test_toggle_task_completion(self, mock_session_local, todo_interface):
        """Test toggling task completion status"""
        # Setup mock session and task
        mock_session = Mock()
        mock_session_local.return_value.__enter__.return_value = mock_session
        
        mock_task = Mock()
        mock_task.completed = False
        mock_session.query.return_value.get.return_value = mock_task
        
        # Test toggling to completed
        todo_interface._toggle_task_completion(1, True)
        
        assert mock_task.completed is True
        mock_session.commit.assert_called_once()
    
    @patch('app.SessionLocal')
    def test_update_task_title(self, mock_session_local, todo_interface):
        """Test updating task title"""
        # Setup mock session and task
        mock_session = Mock()
        mock_session_local.return_value.__enter__.return_value = mock_session
        
        mock_task = Mock()
        mock_task.title = "Old Title"
        mock_session.query.return_value.get.return_value = mock_task
        
        # Test updating title
        new_title = "New Title"
        todo_interface._update_task_title(1, new_title)
        
        assert mock_task.title == new_title
        mock_session.commit.assert_called_once()
    
    @patch('app.SessionLocal')
    def test_delete_task(self, mock_session_local, todo_interface):
        """Test deleting task"""
        # Setup mock session and task
        mock_session = Mock()
        mock_session_local.return_value.__enter__.return_value = mock_session
        
        mock_task = Mock()
        mock_session.query.return_value.get.return_value = mock_task
        
        # Test deleting task
        todo_interface._delete_task(1)
        
        mock_session.delete.assert_called_once_with(mock_task)
        mock_session.commit.assert_called_once()
    
    @patch('app.SessionLocal')
    def test_operations_with_nonexistent_task(self, mock_session_local, todo_interface):
        """Test operations gracefully handle nonexistent tasks"""
        # Setup mock session with no task found
        mock_session = Mock()
        mock_session_local.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.get.return_value = None
        
        # Test operations don't crash with nonexistent task
        todo_interface._toggle_task_completion(999, True)
        todo_interface._update_task_title(999, "New Title")
        todo_interface._delete_task(999)
        
        # Verify no commits were made
        mock_session.commit.assert_not_called()


class TestIntegration(TestTodoInterface):
    """Integration tests for complete TodoInterface workflow"""
    
    def test_complete_task_workflow(self, todo_interface, db_session, sample_user):
        """Test complete workflow: create, edit, toggle, delete"""
        # Patch SessionLocal to use our test session
        with patch('app.SessionLocal') as mock_session_local:
            mock_session_local.return_value.__enter__.return_value = db_session
            
            # 1. Create task
            test_title = "Workflow Test Task"
            todo_interface._save_task(test_title)
            
            # Verify task was created
            task = db_session.query(Task).filter(
                Task.user_id == sample_user.id,
                Task.title == test_title
            ).first()
            assert task is not None
            assert task.completed is False
            
            # 2. Update task title
            new_title = "Updated Workflow Task"
            todo_interface._update_task_title(task.id, new_title)
            
            # Verify title was updated
            db_session.refresh(task)
            assert task.title == new_title
            
            # 3. Toggle completion
            todo_interface._toggle_task_completion(task.id, True)
            
            # Verify completion was toggled
            db_session.refresh(task)
            assert task.completed is True
            
            # 4. Delete task
            todo_interface._delete_task(task.id)
            
            # Verify task was deleted
            deleted_task = db_session.query(Task).filter(Task.id == task.id).first()
            assert deleted_task is None
    
    def test_multiple_tasks_same_date(self, todo_interface, db_session, sample_user):
        """Test handling multiple tasks for the same date"""
        with patch('app.SessionLocal') as mock_session_local:
            mock_session_local.return_value.__enter__.return_value = db_session
            
            # Create multiple tasks
            task_titles = ["Task 1", "Task 2", "Task 3"]
            for title in task_titles:
                todo_interface._save_task(title)
            
            # Verify all tasks were created
            tasks = db_session.query(Task).filter(
                Task.user_id == sample_user.id,
                Task.due_date == todo_interface.date
            ).all()
            
            assert len(tasks) == 3
            saved_titles = [task.title for task in tasks]
            assert set(saved_titles) == set(task_titles)
    
    def test_tasks_isolated_by_user_and_date(self, db_session):
        """Test that tasks are properly isolated by user and date"""
        # Create two users
        user1 = User(name="User1")
        user2 = User(name="User2")
        db_session.add_all([user1, user2])
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)
        
        # Create TodoInterface instances for different users and dates
        date1 = dt.date(2024, 1, 15)
        date2 = dt.date(2024, 1, 16)
        
        interface1 = TodoInterface(user1.id, date1)
        interface2 = TodoInterface(user2.id, date1)
        interface3 = TodoInterface(user1.id, date2)
        
        with patch('app.SessionLocal') as mock_session_local:
            mock_session_local.return_value.__enter__.return_value = db_session
            
            # Create tasks for different combinations
            interface1._save_task("User1 Date1 Task")
            interface2._save_task("User2 Date1 Task")
            interface3._save_task("User1 Date2 Task")
            
            # Verify tasks are properly isolated
            user1_date1_tasks = db_session.query(Task).filter(
                Task.user_id == user1.id,
                Task.due_date == date1
            ).all()
            assert len(user1_date1_tasks) == 1
            assert user1_date1_tasks[0].title == "User1 Date1 Task"
            
            user2_date1_tasks = db_session.query(Task).filter(
                Task.user_id == user2.id,
                Task.due_date == date1
            ).all()
            assert len(user2_date1_tasks) == 1
            assert user2_date1_tasks[0].title == "User2 Date1 Task"
            
            user1_date2_tasks = db_session.query(Task).filter(
                Task.user_id == user1.id,
                Task.due_date == date2
            ).all()
            assert len(user1_date2_tasks) == 1
            assert user1_date2_tasks[0].title == "User1 Date2 Task"


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])