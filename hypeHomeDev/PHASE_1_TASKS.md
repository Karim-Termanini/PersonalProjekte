# Phase 1: `phase-1-dashboard-core` — Task Breakdown

> **Branch:** `phase-1-dashboard-core`
> **Goal:** Build the main application shell with navigation and core UI infrastructure.
> **Agents:** 3 (Agent A, Agent B, Agent C)
> **Strategic Note:** Continue respecting the Flatpak + Docker-first approach for cross-distribution compatibility.

---

## Agent Assignment Overview

| Agent | Focus Area | Deliverables |
|-------|-----------|--------------|
| **Agent A** | Main Application Window & Navigation | Window persistence, sidebar navigation, keyboard shortcuts, page transitions |
| **Agent B** | Settings & Configuration | Settings panel, theme switching, about dialog, configuration management |
| **Agent C** | UI Components & State Management | Global state manager, reusable UI components, error handling, accessibility |

---

## Agent A — Main Application Window & Navigation

### Task A.1: Enhanced Main Window
**Priority:** High
**Dependencies:** Phase 0 A.3

Enhance `src/ui/window.py`:
- Save/restore window position and size (using Gtk.ApplicationWindow `default-width`, `default-height`)
- Wayland compatibility testing
- Proper window close handling with confirmation dialog for unsaved changes
- Window state persistence across sessions

### Task A.2: Sidebar Navigation System
**Priority:** High
**Dependencies:** A.1

Create navigation sidebar with:
- **Sections:**
  - Dashboard (icon: `view-dashboard-symbolic`)
  - Machine Setup (icon: `computer-symbolic`)
  - Extensions (icon: `extension-symbolic`)
  - Utilities (icon: `utilities-symbolic`)
- Hamburger menu button in header bar
- Smooth page transitions (fade/slide animations)
- Active page highlighting
- Responsive design (collapsible sidebar on small screens)

### Task A.3: Keyboard Shortcuts
**Priority:** Medium
**Dependencies:** A.2

Implement keyboard shortcuts:
- `Ctrl+1` - Dashboard
- `Ctrl+2` - Machine Setup
- `Ctrl+3` - Extensions
- `Ctrl+4` - Utilities
- `Ctrl+Q` - Quit application
- `F11` - Toggle fullscreen
- `Ctrl+Comma` - Open settings
- Shortcut customization framework (placeholder)

### Task A.4: Page Content Framework
**Priority:** High
**Dependencies:** A.2

Create page content system:
- Base `Page` class with common functionality
- Page loading/unloading lifecycle
- Lazy loading of page content
- Page state persistence
- Empty state placeholders for each page

### Task A.5: Header Bar Customization
**Priority:** Medium
**Dependencies:** A.1

Enhance header bar:
- Application title with current page
- Page-specific actions (contextual buttons)
- Loading indicators
- Notification badges
- Search bar (placeholder for future)

### Acceptance Criteria (Agent A)
- [ ] Window position/size persists across restarts
- [ ] Sidebar navigation works correctly
- [ ] All keyboard shortcuts function
- [ ] Page transitions are smooth
- [ ] Header bar shows contextual actions

---

## Agent B — Settings & Configuration

### Task B.1: Settings Panel
**Priority:** High
**Dependencies:** Phase 0 A.4

Create settings panel accessible from hamburger menu:
- **Appearance:**
  - Theme preference (light/dark/system)
  - Accent color selection
  - Font size adjustment
- **Behavior:**
  - Auto-start on login (Flatpak portal integration)
  - Default page on startup
  - Confirm before quitting
- **Dashboard:**
  - Default refresh interval
  - Widget animation preferences
- **GitHub:** (placeholder for Phase 3)
- **Extensions:** (placeholder for Phase 6)

### Task B.2: Theme Switching
**Priority:** High
**Dependencies:** B.1

Implement theme switching:
- Detect system theme preference
- Apply theme to entire application
- Live theme switching without restart
- Theme persistence in config
- Test with Libadwaita color schemes

### Task B.3: About Dialog
**Priority:** Medium
**Dependencies:** None

Create about dialog:
- Application name and version (from `pyproject.toml`)
- License information (GPL-3.0-or-later)
- Contributors list (placeholder)
- Links to:
  - GitHub repository
  - Issue tracker
  - Documentation
  - Donation page (placeholder)
- System information (optional)

### Task B.4: Configuration Management Enhancement
**Priority:** Medium
**Dependencies:** Phase 0 A.4

Enhance `ConfigManager`:
- Schema validation for settings
- Migration for config version changes
- Export/import configuration
- Reset to defaults functionality
- Config change notifications via event bus

### Task B.5: Auto-start Integration
**Priority:** Low
**Dependencies:** B.1

Implement auto-start via Flatpak portal:
- Check if auto-start is available
- Enable/disable auto-start
- Desktop entry creation/removal
- Portal permission handling

### Acceptance Criteria (Agent B)
- [ ] Settings panel is accessible and functional
- [ ] Theme switching works correctly
- [ ] About dialog shows correct information
- [ ] Config changes persist across restarts
- [ ] Auto-start integration works (if supported)

---

## Agent C — UI Components & State Management

### Task C.1: Global State Manager Enhancement
**Priority:** High
**Dependencies:** Phase 0 A.5

Enhance `AppState`:
- Page navigation state
- User preferences cache
- Application lifecycle state
- Error state tracking
- Thread-safe state updates
- State change notifications

### Task C.2: Reusable UI Components Library
**Priority:** High
**Dependencies:** None

Create `src/ui/widgets/` components:
- `Card` - Container widget with shadow and padding
- `Button` - Enhanced button with icon support
- `StatusIndicator` - Color-coded status dots
- `LoadingSpinner` - Animated loading indicator
- `EmptyState` - Placeholder for empty content
- `ErrorBanner` - Error display with retry button
- `SectionHeader` - Consistent section headers

### Task C.3: Error Handling System
**Priority:** Medium
**Dependencies:** C.1

Create error handling:
- Toast notifications for user feedback
- Error dialog for critical errors
- Error logging with context
- Error recovery suggestions
- Network error handling
- File permission error handling

### Task C.4: Accessibility Implementation
**Priority:** Medium
**Dependencies:** A.2, C.2

Implement accessibility:
- ARIA labels for all interactive elements
- Keyboard navigation testing
- Screen reader compatibility
- High contrast mode testing
- Focus indicator styling
- RTL layout support infrastructure

### Task C.5: Internationalization Setup
**Priority:** Low
**Dependencies:** None

Set up i18n framework:
- Gettext configuration
- English strings extraction
- Arabic locale placeholder
- Language switcher UI (placeholder)
- RTL layout testing

### Task C.6: Event Bus Enhancement
**Priority:** Medium
**Dependencies:** Phase 0 A.6

Enhance event bus:
- Type hints for events
- Event documentation
- Debug mode for event tracing
- Performance optimization
- Error handling in event handlers

### Acceptance Criteria (Agent C)
- [ ] Global state manages navigation correctly
- [ ] UI components are reusable and consistent
- [ ] Error handling provides user feedback
- [ ] Accessibility features work correctly
- [ ] Event bus delivers events efficiently

---

## Integration Points

### Critical Integration Points

1. **Agent A ↔ Agent B:**
   - Settings panel accessible from hamburger menu
   - Theme changes apply to entire UI
   - Window settings persist in config

2. **Agent A ↔ Agent C:**
   - Navigation state managed by global state
   - UI components used in all pages
   - Error handling for navigation failures

3. **Agent B ↔ Agent C:**
   - Config changes trigger state updates
   - UI components respect theme settings
   - Error handling for config operations

### Cross-Phase Dependencies

- **Phase 0:** All Python infrastructure, config system, event bus
- **Phase 2:** Dashboard page content (placeholder in Phase 1)
- **Phase 3:** GitHub settings section (placeholder in Phase 1)
- **Phase 4:** Machine Setup page content (placeholder in Phase 1)
- **Phase 5:** Utilities page content (placeholder in Phase 1)
- **Phase 6:** Extensions page content (placeholder in Phase 1)

---

## Execution Order & Dependencies

```
Phase 1 Execution Timeline:

┌─────────────────────────────────────────────────────────────┐
│                    PARALLEL START                           │
├───────────────┬──────────────────┬──────────────────────────┤
│  Agent A      │     Agent B      │       Agent C            │
│               │                  │                          │
│  A.1 Window   │  B.1 Settings    │  C.1 State Manager       │
│  A.2 Sidebar  │  B.2 Theme       │  C.2 UI Components       │
│  A.3 Shortcuts│  B.3 About Dialog│  C.3 Error Handling      │
│  A.4 Pages    │  B.4 Config Enh. │  C.4 Accessibility       │
│  A.5 Header   │  B.5 Auto-start  │  C.5 i18n Setup          │
│               │                  │  C.6 Event Bus           │
├───────────────┴──────────────────┴──────────────────────────┤
│                     INTEGRATION                             │
│                                                             │
│  - Connect sidebar to page system                           │
│  - Apply theme to all components                            │
│  - Integrate error handling                                 │
│  - Test navigation flow                                     │
├─────────────────────────────────────────────────────────────┤
│                     FINAL TESTING                           │
│                                                             │
│  - Full navigation testing                                  │
│  - Theme switching testing                                  │
│  - Keyboard shortcut testing                                │
│  - Accessibility testing                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Deliverables Summary

| Agent | Key Files Created/Modified |
|-------|---------------------------|
| **A** | `src/ui/window.py` (enhanced), `src/ui/navigation.py`, `src/ui/pages/` (base classes), keyboard shortcuts system |
| **B** | `src/ui/settings.py`, `src/config/theme.py`, about dialog, config enhancements |
| **C** | `src/ui/widgets/` (component library), enhanced `AppState`, error handling system, accessibility features |

---

## Testing Requirements

### Manual Testing
1. **Navigation:**
   - Click all sidebar items
   - Test keyboard shortcuts
   - Test page transitions
   - Test window resize/position persistence

2. **Settings:**
   - Change theme (light/dark/system)
   - Modify settings and restart app
   - Open about dialog
   - Test auto-start (if available)

3. **UI/UX:**
   - Test on different screen sizes
   - Test with screen reader
   - Test keyboard-only navigation
   - Test error scenarios

### Automated Testing
- Navigation unit tests
- Config persistence tests
- Theme switching tests
- UI component tests
- Accessibility test suite

---

## Success Metrics

1. **Performance:**
   - App starts in <2s with Phase 1 features
   - Page transitions complete in <200ms
   - Memory usage <150MB

2. **Usability:**
   - All navigation paths work correctly
   - Settings persist across sessions
   - Keyboard shortcuts are responsive

3. **Quality:**
   - No crashes during navigation
   - All tests pass
   - No accessibility violations
   - Code coverage >70% for new code

---

## Ready for Phase 2

Upon completion of Phase 1, the application will have:
- ✅ Complete navigation system
- ✅ Settings management
- ✅ Theme support
- ✅ Reusable UI components
- ✅ Error handling
- ✅ Accessibility foundation

This sets the stage for Phase 2: Dashboard System Widgets.

---

*Phase 1 builds upon the solid foundation established in Phase 0, creating a professional, navigable application shell ready for feature implementation in subsequent phases.*