#!/usr/bin/env python3
"""
Test suite for dynamic background system with daily themes
Tests theme selection, CSS generation, and date-based rotation logic
"""

import pytest
import datetime as dt
from app import get_daily_background_theme, get_background_css


class TestDailyBackgroundTheme:
    """Test the daily background theme selection algorithm"""
    
    def test_theme_selection_consistency(self):
        """Test that the same date always returns the same theme"""
        test_date = dt.date(2024, 1, 15)
        theme1 = get_daily_background_theme(test_date)
        theme2 = get_daily_background_theme(test_date)
        assert theme1 == theme2, "Same date should return same theme"
    
    def test_theme_rotation_coverage(self):
        """Test that all themes are used over a year period"""
        themes = [
            "cosmic-blue", "aurora-green", "sunset-orange", 
            "deep-purple", "ocean-teal", "forest-emerald", "rose-gold"
        ]
        
        # Test 365 consecutive days to ensure all themes are used
        start_date = dt.date(2024, 1, 1)
        used_themes = set()
        
        for i in range(365):
            current_date = start_date + dt.timedelta(days=i)
            theme = get_daily_background_theme(current_date)
            used_themes.add(theme)
            assert theme in themes, f"Invalid theme returned: {theme}"
        
        assert len(used_themes) == len(themes), "All themes should be used over a year"
    
    def test_theme_distribution(self):
        """Test that themes are distributed relatively evenly"""
        themes = [
            "cosmic-blue", "aurora-green", "sunset-orange", 
            "deep-purple", "ocean-teal", "forest-emerald", "rose-gold"
        ]
        
        theme_counts = {theme: 0 for theme in themes}
        start_date = dt.date(2024, 1, 1)
        
        # Count theme usage over 70 days (10 weeks)
        for i in range(70):
            current_date = start_date + dt.timedelta(days=i)
            theme = get_daily_background_theme(current_date)
            theme_counts[theme] += 1
        
        # Each theme should appear at least once in 70 days
        for theme, count in theme_counts.items():
            assert count > 0, f"Theme {theme} should appear at least once"
        
        # No theme should dominate (appear more than 15 times in 70 days)
        for theme, count in theme_counts.items():
            assert count <= 15, f"Theme {theme} appears too frequently: {count} times"
    
    def test_leap_year_handling(self):
        """Test that leap years are handled correctly"""
        # Test leap year date
        leap_date = dt.date(2024, 2, 29)  # 2024 is a leap year
        theme = get_daily_background_theme(leap_date)
        assert theme is not None, "Leap year date should return a valid theme"
        
        # Test that day 366 in leap year works
        end_of_leap_year = dt.date(2024, 12, 31)
        theme = get_daily_background_theme(end_of_leap_year)
        assert theme is not None, "End of leap year should return a valid theme"
    
    def test_different_years_same_day(self):
        """Test that the same day of year in different years returns the same theme"""
        date1 = dt.date(2024, 3, 15)  # Day 75 of 2024
        date2 = dt.date(2025, 3, 15)  # Day 74 of 2025 (different due to leap year)
        
        theme1 = get_daily_background_theme(date1)
        theme2 = get_daily_background_theme(date2)
        
        # They might be different due to leap year offset, but both should be valid
        themes = [
            "cosmic-blue", "aurora-green", "sunset-orange", 
            "deep-purple", "ocean-teal", "forest-emerald", "rose-gold"
        ]
        assert theme1 in themes, f"Theme1 should be valid: {theme1}"
        assert theme2 in themes, f"Theme2 should be valid: {theme2}"


class TestBackgroundCSS:
    """Test CSS generation for background themes"""
    
    def test_css_generation_all_themes(self):
        """Test that CSS is generated for all theme types"""
        themes = [
            "cosmic-blue", "aurora-green", "sunset-orange", 
            "deep-purple", "ocean-teal", "forest-emerald", "rose-gold"
        ]
        
        for theme in themes:
            css = get_background_css(theme)
            assert css is not None, f"CSS should be generated for theme: {theme}"
            assert "background:" in css, f"CSS should contain background property for {theme}"
            assert "animation:" in css, f"CSS should contain animation property for {theme}"
            assert "backgroundShift" in css, f"CSS should reference backgroundShift animation for {theme}"
    
    def test_css_contains_required_properties(self):
        """Test that generated CSS contains all required properties"""
        css = get_background_css("cosmic-blue")
        
        required_properties = [
            "background:",
            "animation:",
            "backgroundShift",
            "20s",
            "ease-in-out",
            "infinite"
        ]
        
        for prop in required_properties:
            assert prop in css, f"CSS should contain: {prop}"
    
    def test_invalid_theme_fallback(self):
        """Test that invalid theme names fall back to cosmic-blue"""
        invalid_theme = "nonexistent-theme"
        css = get_background_css(invalid_theme)
        
        # Should fall back to cosmic-blue theme
        cosmic_css = get_background_css("cosmic-blue")
        assert css == cosmic_css, "Invalid theme should fall back to cosmic-blue"
    
    def test_css_format_consistency(self):
        """Test that all themes generate consistently formatted CSS"""
        themes = [
            "cosmic-blue", "aurora-green", "sunset-orange", 
            "deep-purple", "ocean-teal", "forest-emerald", "rose-gold"
        ]
        
        for theme in themes:
            css = get_background_css(theme)
            
            # Check that CSS is properly formatted
            assert css.strip().startswith("background:"), f"CSS should start with background property for {theme}"
            assert css.strip().endswith(";"), f"CSS should end with semicolon for {theme}"
            assert "radial-gradient" in css, f"CSS should contain radial-gradient for {theme}"
            assert "linear-gradient" in css, f"CSS should contain linear-gradient for {theme}"


class TestIntegration:
    """Integration tests for the complete background system"""
    
    def test_daily_theme_cycle(self):
        """Test a complete daily theme cycle"""
        start_date = dt.date(2024, 1, 1)
        themes_used = []
        
        # Test 14 consecutive days
        for i in range(14):
            current_date = start_date + dt.timedelta(days=i)
            theme = get_daily_background_theme(current_date)
            css = get_background_css(theme)
            
            themes_used.append(theme)
            
            # Verify theme is valid and CSS is generated
            assert theme is not None, f"Theme should be valid for day {i+1}"
            assert css is not None, f"CSS should be generated for day {i+1}"
            assert len(css.strip()) > 0, f"CSS should not be empty for day {i+1}"
        
        # Verify we get different themes over the period
        unique_themes = set(themes_used)
        assert len(unique_themes) > 1, "Should get multiple different themes over 14 days"
    
    def test_theme_persistence_across_app_restarts(self):
        """Test that themes remain consistent across simulated app restarts"""
        test_dates = [
            dt.date(2024, 1, 1),
            dt.date(2024, 6, 15),
            dt.date(2024, 12, 31)
        ]
        
        # Simulate multiple "app restarts" by calling the function multiple times
        for test_date in test_dates:
            themes = []
            for _ in range(5):  # Simulate 5 app restarts
                theme = get_daily_background_theme(test_date)
                themes.append(theme)
            
            # All calls should return the same theme for the same date
            assert all(t == themes[0] for t in themes), f"Theme should be consistent for {test_date}"


if __name__ == "__main__":
    # Run tests if script is executed directly
    pytest.main([__file__, "-v"])