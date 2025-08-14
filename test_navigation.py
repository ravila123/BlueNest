"""
Tests for the enhanced navigation system with user/context separation
"""
import pytest
import datetime as dt
from unittest.mock import Mock, patch
import sys
import os

# Add the current directory to the path so we can import from app.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import NavigationState, get_available_views


class TestNavigationState:
    """Test the NavigationState class functionality"""
    
    def test_initialization(self):
        """Test NavigationState initializes with correct defaults"""
        nav_state = NavigationState()
        assert nav_state.active_user == "Ravi"
        assert nav_state.current_view == "todo"
    
    def test_set_active_user_individual(self):
        """Test setting active user to individual user"""
        nav_state = NavigationState()
        nav_state.set_active_user("Amitha")
        
        assert nav_state.active_user == "Amitha"
        assert nav_state.current_view == "todo"  # Should remain valid
    
    def test_set_active_user_common(self):
        """Test setting active user to Common resets view appropriately"""
        nav_state = NavigationState()
        nav_state.current_view = "todo"  # Start with todo view
        nav_state.set_active_user("Common")
        
        assert nav_state.active_user == "Common"
        assert nav_state.current_view == "dashboard"  # Should reset to first available view
    
    def test_set_current_view_valid(self):
        """Test setting a valid view for the current user"""
        nav_state = NavigationState()
        nav_state.active_user = "Ravi"
        nav_state.set_current_view("dashboard")
        
        assert nav_state.current_view == "dashboard"
    
    def test_set_current_view_invalid(self):
        """Test setting an invalid view is ignored"""
        nav_state = NavigationState()
        nav_state.active_user = "Ravi"
        nav_state.current_view = "todo"
        nav_state.set_current_view("wishlist")  # Not available for individual users
        
        assert nav_state.current_view == "todo"  # Should remain unchanged
    
    def test_get_state(self):
        """Test getting navigation state as dictionary"""
        nav_state = NavigationState()
        nav_state.active_user = "Amitha"
        nav_state.current_view = "dashboard"
        
        state = nav_state.get_state()
        
        assert state["active_user"] == "Amitha"
        assert state["current_view"] == "dashboard"
        assert "available_views" in state
        assert isinstance(state["available_views"], list)


class TestGetAvailableViews:
    """Test the get_available_views function"""
    
    def test_common_user_views(self):
        """Test available views for Common user"""
        views = get_available_views("Common")
        expected_views = ["dashboard", "wishlist", "vision_board", "travel_goals"]
        
        assert views == expected_views
        assert "todo" not in views
    
    def test_individual_user_views(self):
        """Test available views for individual users"""
        ravi_views = get_available_views("Ravi")
        amitha_views = get_available_views("Amitha")
        expected_views = ["todo", "dashboard"]
        
        assert ravi_views == expected_views
        assert amitha_views == expected_views
        assert "wishlist" not in ravi_views
        assert "vision_board" not in amitha_views
        assert "travel_goals" not in ravi_views
    
    def test_unknown_user_defaults_to_individual(self):
        """Test that unknown users get individual user views"""
        views = get_available_views("UnknownUser")
        expected_views = ["todo", "dashboard"]
        
        assert views == expected_views


class TestNavigationIntegration:
    """Integration tests for navigation state management"""
    
    def test_user_switch_workflow(self):
        """Test complete workflow of switching between users"""
        nav_state = NavigationState()
        
        # Start with Ravi
        assert nav_state.active_user == "Ravi"
        assert nav_state.current_view == "todo"
        
        # Switch to dashboard view
        nav_state.set_current_view("dashboard")
        assert nav_state.current_view == "dashboard"
        
        # Switch to Common user
        nav_state.set_active_user("Common")
        assert nav_state.active_user == "Common"
        assert nav_state.current_view == "dashboard"  # Should remain valid
        
        # Try to switch to todo (invalid for Common)
        nav_state.set_current_view("todo")
        assert nav_state.current_view == "dashboard"  # Should remain unchanged
        
        # Switch to valid view for Common
        nav_state.set_current_view("wishlist")
        assert nav_state.current_view == "wishlist"
        
        # Switch back to individual user
        nav_state.set_active_user("Amitha")
        assert nav_state.active_user == "Amitha"
        assert nav_state.current_view == "todo"  # Should reset to first available
    
    def test_view_filtering_consistency(self):
        """Test that view filtering is consistent across user switches"""
        nav_state = NavigationState()
        
        # Test all user types
        users_and_expected_views = [
            ("Ravi", ["todo", "dashboard"]),
            ("Amitha", ["todo", "dashboard"]),
            ("Common", ["dashboard", "wishlist", "vision_board", "travel_goals"])
        ]
        
        for user, expected_views in users_and_expected_views:
            nav_state.set_active_user(user)
            available_views = get_available_views(nav_state.active_user)
            
            assert available_views == expected_views
            assert nav_state.current_view in available_views
    
    def test_state_persistence_simulation(self):
        """Test that navigation state can be properly serialized/deserialized"""
        nav_state = NavigationState()
        nav_state.set_active_user("Common")
        nav_state.set_current_view("vision_board")
        
        # Simulate saving state
        state_dict = nav_state.get_state()
        
        # Simulate loading state
        new_nav_state = NavigationState()
        new_nav_state.active_user = state_dict["active_user"]
        new_nav_state.current_view = state_dict["current_view"]
        
        assert new_nav_state.active_user == "Common"
        assert new_nav_state.current_view == "vision_board"
        assert new_nav_state.get_state() == state_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])