# Enhanced Ask Blue Chat Interface Implementation
import re
import datetime as dt
from typing import Optional, List, Tuple
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# This will be integrated into app.py

class BlueAssistant:
    """Enhanced Ask Blue AI assistant with cross-user data aggregation and contextual responses"""
    
    def __init__(self):
        self.greeting = "Hey! It's Blue Boy!! What do you want to know from me?"
    
    def process_query(self, query: str, user_context: str) -> str:
        """Enhanced query processing with cross-user data aggregation and contextual responses"""
        if not query.strip():
            return self.greeting
        
        query_lower = query.lower()
        today = dt.date.today()
        
        # Enhanced query type detection
        if self._is_date_query(query_lower):
            return self._handle_date_query(query, user_context, today)
        elif self._is_goal_query(query_lower):
            return self._handle_goal_query(query, user_context)
        elif self._is_activity_query(query_lower):
            return self._handle_activity_query(query, user_context, today)
        elif self._is_completion_query(query_lower):
            return self._handle_completion_query(query, user_context, today)
        elif self._is_vision_board_query(query_lower):
            return self._handle_vision_board_query(query, user_context)
        elif self._is_rollover_query(query_lower):
            return self._handle_rollover_query(query, user_context)
        else:
            return self._provide_help_suggestions()
    
    def _is_date_query(self, query: str) -> bool:
        """Check if query is asking about a specific date"""
        date_indicators = [
            "what did", "what happened", "what was", "on april", "on march", 
            "yesterday", "today", "tomorrow", "last week", "this week",
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
        ]
        return any(indicator in query for indicator in date_indicators)
    
    def _is_goal_query(self, query: str) -> bool:
        """Check if query is asking about goals"""
        goal_indicators = ["goal", "goals", "target", "objective", "plan", "planning"]
        return any(indicator in query for indicator in goal_indicators)
    
    def _is_activity_query(self, query: str) -> bool:
        """Check if query is asking about activities or tasks"""
        activity_indicators = ["activity", "activities", "task", "tasks", "doing", "completed", "working on"]
        return any(indicator in query for indicator in activity_indicators)
    
    def _is_completion_query(self, query: str) -> bool:
        """Check if query is asking about completion rates or progress"""
        completion_indicators = ["completion", "progress", "finished", "done", "completed", "rate"]
        return any(indicator in query for indicator in completion_indicators)
    
    def _is_vision_board_query(self, query: str) -> bool:
        """Check if query is asking about vision board"""
        vision_indicators = ["vision", "vision board", "dreams", "aspirations", "inspiration"]
        return any(indicator in query for indicator in vision_indicators)
    
    def _is_rollover_query(self, query: str) -> bool:
        """Check if query is asking about task rollovers"""
        rollover_indicators = ["rollover", "rolled over", "incomplete", "unfinished", "pending"]
        return any(indicator in query for indicator in rollover_indicators)
    
    def _provide_help_suggestions(self) -> str:
        """Provide helpful suggestions for queries"""
        return ("🐶 **I can help you with:**\n\n"
                "📅 **Dates**: \"What did I do on April 10?\", \"What did we do yesterday?\"\n"
                "🎯 **Goals**: \"What's my fitness goal?\", \"Show me travel goals\"\n"
                "📋 **Activities**: \"What am I working on?\", \"Recent activities\"\n"
                "📊 **Progress**: \"Weekly completion rate\", \"How am I doing?\"\n"
                "🎨 **Vision Board**: \"What's on my vision board?\"\n"
                "🔄 **Rollovers**: \"Which tasks keep rolling over?\"\n\n"
                "Try asking me anything about your productivity data!")