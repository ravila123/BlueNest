# Requirements Document

## Introduction

This feature involves a complete UI/UX redesign of the BlueNest to-do application to create a highly aesthetic, minimal, and user-friendly experience. The redesign focuses on improving navigation, visual appeal, user experience, and functionality while maintaining the core productivity features. The new design will feature a clean dark-mode interface with dynamic backgrounds, improved task management, enhanced navigation, and an integrated AI assistant.

## Requirements

### Requirement 1: Navigation and Layout Restructure

**User Story:** As a user, I want a clean and intuitive navigation system that separates personal and shared content appropriately, so that I can easily access the right features for each context.

#### Acceptance Criteria

1. WHEN the application loads THEN the system SHALL display a left side panel with "Active User" selector (Ravi / Amitha / Common)
2. WHEN "Common" is selected THEN the system SHALL only show Wishlist, Vision Board, and Travel Goals options
3. WHEN an individual user (Ravi/Amitha) is selected THEN the system SHALL only show To-Do List option
4. WHEN a user switches between users THEN the system SHALL remove current daily/weekly/monthly tabs from the right side and move them into the main panel based on the selected user
5. WHEN navigating between sections THEN the system SHALL maintain consistent layout and visual hierarchy

### Requirement 2: Enhanced To-Do List Experience

**User Story:** As a user, I want a streamlined daily to-do experience similar to Microsoft Teams to-do list with intuitive editing and navigation, so that I can quickly manage my tasks without UI friction.

#### Acceptance Criteria

1. WHEN viewing the Daily View THEN the system SHALL display the to-do list as the main POV (point of view) with date and day at the top
2. WHEN clicking on the to-do input area THEN the system SHALL allow immediate note-taking like Microsoft Teams to-do list
3. WHEN pressing Enter in the task input THEN the system SHALL save the to-do item automatically and move cursor to the next line for a new item
4. WHEN clicking on the next line THEN the system SHALL save the current to-do item and create a new input field
5. WHEN creating or editing tasks THEN the system SHALL provide simple text editor with bullet points, bold, italics formatting options
6. WHEN a day ends with incomplete tasks THEN the system SHALL auto-rollover incomplete tasks to the next day
7. WHEN swiping left/right THEN the system SHALL provide quick day navigation limited to 7 days backward/forward
8. WHEN accessing dates older than 7 days THEN the system SHALL provide a calendar picker interface
9. WHEN adding new items THEN the system SHALL ensure items align neatly without creating awkward squares or misaligned elements
10. WHEN interacting with to-do items THEN the system SHALL provide seamless, instant saving without explicit save buttons

### Requirement 3: Visual Design and Aesthetics

**User Story:** As a user, I want a beautiful and cozy interface that changes dynamically, so that using the application feels pleasant and engaging.

#### Acceptance Criteria

1. WHEN the application loads THEN the system SHALL display a very aesthetic, minimal dark-mode theme with cozy background
2. WHEN the application runs THEN the system SHALL feature an aesthetic moving wallpaper that changes everyday
3. WHEN displaying UI elements THEN the system SHALL remove emoji-auto-addition feature from task creation
4. WHEN showing tasks THEN the system SHALL remove "common" option in to-do entry interface
5. WHEN rendering the interface THEN the system SHALL ensure all visual elements follow consistent aesthetic principles

### Requirement 4: Notebook and Vision Board Reorganization

**User Story:** As a user, I want dedicated spaces for creative content like notes and vision boards that are separate from task management, so that I can organize different types of content appropriately.

#### Acceptance Criteria

1. WHEN accessing the notebook THEN the system SHALL remove it from the to-do list page entirely
2. WHEN viewing the right tab panel THEN the system SHALL move the notebook into a dedicated notebook view
3. WHEN using the Vision Board THEN the system SHALL treat it like a blank canvas/empty notebook
4. WHEN adding content to Vision Board THEN the system SHALL allow dropping images, videos, or text directly (like iOS Notes app)
5. WHEN displaying media in Vision Board THEN the system SHALL show actual images inline (not as attachments)
6. WHEN accessing Vision Board THEN the system SHALL work for both Ravi & Amitha under "Common" tab

### Requirement 5: Ask Blue AI Assistant Integration

**User Story:** As a user, I want an easily accessible AI assistant that can help me query my data and provide insights, so that I can quickly get information about my activities and goals.

#### Acceptance Criteria

1. WHEN viewing any page THEN the system SHALL display a small, floating dog icon in the top right corner
2. WHEN clicking the dog icon THEN the system SHALL open a small chat square (not full screen)
3. WHEN the chat opens THEN the system SHALL display greeting: "Hey! It's Blue Boy!! What do you want to know from me?"
4. WHEN asking queries THEN the system SHALL answer questions like "What did I do on April 10th?", "What did we do on April 11th?", "What's my fitness goal of the year?"
5. WHEN processing queries THEN the system SHALL pull data from both Ravi's and Amitha's to-dos, wishlist, vision board, etc.
6. WHEN handling "Common" queries THEN the system SHALL summarize combined data appropriately

### Requirement 6: Enhanced Dashboard

**User Story:** As a user, I want a comprehensive dashboard that gives me an overview of my goals and recent activities, so that I can stay motivated and track my progress.

#### Acceptance Criteria

1. WHEN accessing the dashboard THEN the system SHALL summarize Vision Board highlights
2. WHEN viewing the dashboard THEN the system SHALL display Quarterly/Yearly goals
3. WHEN checking the dashboard THEN the system SHALL show recent to-do completions
4. WHEN using the dashboard THEN the system SHALL maintain the Ask Blue feature in the top right corner with Dog icon
5. WHEN Ask Blue is activated from dashboard THEN the system SHALL hover a small window with greeting message

### Requirement 7: User Experience Improvements

**User Story:** As a user, I want smooth interactions and intuitive controls throughout the application, so that I can focus on productivity rather than learning the interface.

#### Acceptance Criteria

1. WHEN interacting with any UI element THEN the system SHALL provide smooth, responsive feedback
2. WHEN navigating between sections THEN the system SHALL maintain visual continuity and context
3. WHEN performing common actions THEN the system SHALL minimize the number of clicks/steps required
4. WHEN using touch/swipe gestures THEN the system SHALL respond appropriately and provide visual feedback
5. WHEN the interface updates THEN the system SHALL use smooth transitions and animations where appropriate