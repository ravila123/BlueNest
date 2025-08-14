#!/usr/bin/env python3
"""
Demo script for swipe navigation functionality
Shows how the swipe navigation system works with different scenarios
"""

import datetime as dt
from app import handle_swipe_navigation

def demo_swipe_navigation():
    """Demonstrate swipe navigation functionality"""
    print("🎯 BlueNest Swipe Navigation Demo")
    print("=" * 50)
    
    today = dt.date.today()
    user_id = 1
    
    print(f"📅 Today: {today.strftime('%A, %B %d, %Y')}")
    print()
    
    # Test scenarios
    scenarios = [
        ("Today → Next Day", today, "next"),
        ("Today → Previous Day", today, "prev"),
        ("3 Days Forward → Next Day", today + dt.timedelta(days=3), "next"),
        ("3 Days Back → Previous Day", today - dt.timedelta(days=3), "prev"),
        ("7 Days Forward → Next Day (Should Fail)", today + dt.timedelta(days=7), "next"),
        ("7 Days Back → Previous Day (Should Fail)", today - dt.timedelta(days=7), "prev"),
        ("6 Days Forward → Next Day (At Limit)", today + dt.timedelta(days=6), "next"),
        ("6 Days Back → Previous Day (At Limit)", today - dt.timedelta(days=6), "prev"),
    ]
    
    for description, current_date, direction in scenarios:
        print(f"🔄 {description}")
        print(f"   Current: {current_date.strftime('%A, %B %d')}")
        
        new_date, success, message = handle_swipe_navigation(user_id, direction, current_date)
        
        if success:
            print(f"   ✅ Success: {new_date.strftime('%A, %B %d')}")
            print(f"   📝 Message: {message}")
        else:
            print(f"   ❌ Failed: {message}")
            print(f"   📅 Date unchanged: {new_date.strftime('%A, %B %d')}")
        
        print()
    
    # Demonstrate navigation sequence
    print("🔄 Navigation Sequence Demo")
    print("-" * 30)
    
    current_date = today
    print(f"Starting from: {current_date.strftime('%A, %B %d')}")
    
    # Navigate forward 7 days
    for i in range(8):  # Try 8 to show the limit
        new_date, success, message = handle_swipe_navigation(user_id, "next", current_date)
        if success:
            current_date = new_date
            print(f"Day {i+1}: ✅ {current_date.strftime('%A, %B %d')}")
        else:
            print(f"Day {i+1}: ❌ {message}")
            break
    
    print()
    print("🎉 Demo Complete!")
    print()
    print("📱 In the actual app, users can:")
    print("   • Swipe left to go to next day")
    print("   • Swipe right to go to previous day")
    print("   • Use calendar picker for dates beyond 7-day range")
    print("   • See visual feedback during swipe gestures")
    print("   • Get helpful error messages when limits are reached")

if __name__ == "__main__":
    demo_swipe_navigation()