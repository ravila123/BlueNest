#!/usr/bin/env python3
"""
Demo script to show different daily background themes
"""

import datetime as dt
from app import get_daily_background_theme, get_background_css

def demo_themes():
    """Demonstrate the daily background theme system"""
    print("🎨 BlueNest Dynamic Background Theme System Demo")
    print("=" * 50)
    
    # Show today's theme
    today = dt.date.today()
    today_theme = get_daily_background_theme(today)
    print(f"📅 Today ({today.strftime('%B %d, %Y')}): {today_theme}")
    
    print("\n🔄 Theme Rotation for Next 14 Days:")
    print("-" * 40)
    
    for i in range(14):
        date = today + dt.timedelta(days=i)
        theme = get_daily_background_theme(date)
        day_name = date.strftime('%A')
        date_str = date.strftime('%m/%d')
        print(f"{day_name:>9} {date_str}: {theme}")
    
    print("\n🎨 Available Themes:")
    print("-" * 20)
    themes = [
        "cosmic-blue", "aurora-green", "sunset-orange", 
        "deep-purple", "ocean-teal", "forest-emerald", "rose-gold"
    ]
    
    for theme in themes:
        css = get_background_css(theme)
        print(f"• {theme}")
        print(f"  CSS: {css[:80]}...")
    
    print(f"\n✨ Total themes available: {len(themes)}")
    print("🔄 Themes rotate daily based on day of year")
    print("🎯 Same date always gets same theme for consistency")

if __name__ == "__main__":
    demo_themes()