#!/usr/bin/env python3
"""
Test suite for swipe navigation functionality in BlueNest
Tests swipe gesture detection, date boundary validation, and navigation logic
"""

import pytest
import datetime as dt
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add the app directory to the path so we can import from app.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import handle_swipe_navigation, get_swipe_navigation_js


class TestSwipeNavigation:
    """Test suite for swipe navigation functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.today = dt.date.today()
        self.user_id = 1
        
    def test_handle_swipe_navigation_next_within_limit(self):
        """Test swipe next navigation within 7-day limit"""
        current_date = self.today + dt.timedelta(days=3)  # 3 days from today
        
        new_date, success, message = handle_swipe_navigation(
            self.user_id, "next", current_date
        )
        
        expected_date = current_date + dt.timedelta(days=1)
        assert success is True
        assert new_date == expected_date
        assert "Moved to" in message
        assert expected_date.strftime('%A, %B %d') in message
    
    def test_handle_swipe_navigation_next_at_limit(self):
        """Test swipe next navigation at 7-day limit boundary"""
        current_date = self.today + dt.timedelta(days=7)  # At 7-day limit
        
        new_date, success, message = handle_swipe_navigation(
            self.user_id, "next", current_date
        )
        
        # Should fail because it would exceed 7-day limit
        assert success is False
        assert new_date == current_date  # Date unchanged
        assert "Cannot navigate more than 7 days into the future" in message
    
    def test_handle_swipe_navigation_prev_within_limit(self):
        """Test swipe previous navigation within 7-day limit"""
        current_date = self.today - dt.timedelta(days=3)  # 3 days before today
        
        new_date, success, message = handle_swipe_navigation(
            self.user_id, "prev", current_date
        )
        
        expected_date = current_date - dt.timedelta(days=1)
        assert success is True
        assert new_date == expected_date
        assert "Moved to" in message
        assert expected_date.strftime('%A, %B %d') in message
    
    def test_handle_swipe_navigation_prev_at_limit(self):
        """Test swipe previous navigation at 7-day limit boundary"""
        current_date = self.today - dt.timedelta(days=7)  # At 7-day limit
        
        new_date, success, message = handle_swipe_navigation(
            self.user_id, "prev", current_date
        )
        
        # Should fail because it would exceed 7-day limit
        assert success is False
        assert new_date == current_date  # Date unchanged
        assert "Cannot navigate more than 7 days into the past" in message
        assert "Use calendar picker for older dates" in message
    
    def test_handle_swipe_navigation_today_next(self):
        """Test swipe next from today"""
        current_date = self.today
        
        new_date, success, message = handle_swipe_navigation(
            self.user_id, "next", current_date
        )
        
        expected_date = self.today + dt.timedelta(days=1)
        assert success is True
        assert new_date == expected_date
        assert "Moved to" in message
    
    def test_handle_swipe_navigation_today_prev(self):
        """Test swipe previous from today"""
        current_date = self.today
        
        new_date, success, message = handle_swipe_navigation(
            self.user_id, "prev", current_date
        )
        
        expected_date = self.today - dt.timedelta(days=1)
        assert success is True
        assert new_date == expected_date
        assert "Moved to" in message
    
    def test_handle_swipe_navigation_invalid_direction(self):
        """Test swipe navigation with invalid direction"""
        current_date = self.today
        
        new_date, success, message = handle_swipe_navigation(
            self.user_id, "invalid", current_date
        )
        
        assert success is False
        assert new_date == current_date  # Date unchanged
        assert message == "Invalid direction"
    
    def test_handle_swipe_navigation_boundary_conditions(self):
        """Test various boundary conditions for swipe navigation"""
        test_cases = [
            # (current_date_offset, direction, should_succeed)
            (-6, "prev", True),   # 6 days back, go to 7 days back (at limit)
            (-7, "prev", False),  # 7 days back, cannot go further
            (-8, "prev", False),  # 8 days back, cannot go further
            (6, "next", True),    # 6 days forward, go to 7 days forward (at limit)
            (7, "next", False),   # 7 days forward, cannot go further
            (8, "next", False),   # 8 days forward, cannot go further
        ]
        
        for offset, direction, should_succeed in test_cases:
            current_date = self.today + dt.timedelta(days=offset)
            new_date, success, message = handle_swipe_navigation(
                self.user_id, direction, current_date
            )
            
            assert success == should_succeed, f"Failed for offset {offset}, direction {direction}"
            
            if should_succeed:
                expected_offset = offset + (1 if direction == "next" else -1)
                expected_date = self.today + dt.timedelta(days=expected_offset)
                assert new_date == expected_date
                assert "Moved to" in message
            else:
                assert new_date == current_date  # Date unchanged
                assert "Cannot navigate more than 7 days" in message


class TestSwipeNavigationJavaScript:
    """Test suite for JavaScript generation and configuration"""
    
    def test_get_swipe_navigation_js_generates_valid_script(self):
        """Test that JavaScript generation produces valid script tag"""
        user_id = 123
        js_code = get_swipe_navigation_js(user_id)
        
        assert "<script>" in js_code
        assert "</script>" in js_code
        assert "function" in js_code
        assert "touchstart" in js_code
        assert "touchmove" in js_code
        assert "touchend" in js_code
    
    def test_get_swipe_navigation_js_contains_configuration(self):
        """Test that JavaScript contains proper configuration constants"""
        user_id = 123
        js_code = get_swipe_navigation_js(user_id)
        
        # Check for configuration constants
        assert "SWIPE_THRESHOLD" in js_code
        assert "SWIPE_VELOCITY_THRESHOLD" in js_code
        assert "MAX_VERTICAL_DEVIATION" in js_code
        assert "SWIPE_TIMEOUT" in js_code
        assert "SWIPE_COOLDOWN" in js_code
    
    def test_get_swipe_navigation_js_contains_visual_feedback(self):
        """Test that JavaScript contains visual feedback functionality"""
        user_id = 123
        js_code = get_swipe_navigation_js(user_id)
        
        assert "swipeIndicator" in js_code
        assert "showSwipeIndicator" in js_code
        assert "createSwipeIndicator" in js_code
        assert "Next Day" in js_code
        assert "Previous Day" in js_code
    
    def test_get_swipe_navigation_js_contains_button_integration(self):
        """Test that JavaScript integrates with existing navigation buttons"""
        user_id = 123
        js_code = get_swipe_navigation_js(user_id)
        
        assert "triggerSwipeNavigation" in js_code
        assert "targetButton" in js_code
        assert "click()" in js_code
        assert "disabled" in js_code
    
    def test_get_swipe_navigation_js_different_user_ids(self):
        """Test that JavaScript generation works with different user IDs"""
        user_ids = [1, 42, 999, 12345]
        
        for user_id in user_ids:
            js_code = get_swipe_navigation_js(user_id)
            assert "<script>" in js_code
            assert "</script>" in js_code
            assert len(js_code) > 1000  # Should be substantial code


class TestSwipeNavigationIntegration:
    """Integration tests for swipe navigation with date boundaries"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.today = dt.date.today()
        self.user_id = 1
    
    def test_seven_day_forward_navigation_sequence(self):
        """Test navigating forward through all 7 allowed days"""
        current_date = self.today
        
        for i in range(7):
            new_date, success, message = handle_swipe_navigation(
                self.user_id, "next", current_date
            )
            
            assert success is True, f"Failed at day {i+1}"
            assert new_date == current_date + dt.timedelta(days=1)
            current_date = new_date
        
        # 8th day should fail
        new_date, success, message = handle_swipe_navigation(
            self.user_id, "next", current_date
        )
        assert success is False
        assert "Cannot navigate more than 7 days into the future" in message
    
    def test_seven_day_backward_navigation_sequence(self):
        """Test navigating backward through all 7 allowed days"""
        current_date = self.today
        
        for i in range(7):
            new_date, success, message = handle_swipe_navigation(
                self.user_id, "prev", current_date
            )
            
            assert success is True, f"Failed at day {i+1}"
            assert new_date == current_date - dt.timedelta(days=1)
            current_date = new_date
        
        # 8th day should fail
        new_date, success, message = handle_swipe_navigation(
            self.user_id, "prev", current_date
        )
        assert success is False
        assert "Cannot navigate more than 7 days into the past" in message
    
    def test_mixed_navigation_within_boundaries(self):
        """Test mixed forward and backward navigation within boundaries"""
        current_date = self.today
        
        # Go forward 3 days
        for _ in range(3):
            current_date, success, _ = handle_swipe_navigation(
                self.user_id, "next", current_date
            )
            assert success is True
        
        # Go back 2 days
        for _ in range(2):
            current_date, success, _ = handle_swipe_navigation(
                self.user_id, "prev", current_date
            )
            assert success is True
        
        # Should be 1 day forward from today
        assert current_date == self.today + dt.timedelta(days=1)
        
        # Go forward 6 more days (should reach limit)
        for i in range(6):
            current_date, success, _ = handle_swipe_navigation(
                self.user_id, "next", current_date
            )
            assert success is True
        
        # Should be at 7 days forward
        assert current_date == self.today + dt.timedelta(days=7)
        
        # One more should fail
        new_date, success, _ = handle_swipe_navigation(
            self.user_id, "next", current_date
        )
        assert success is False


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])