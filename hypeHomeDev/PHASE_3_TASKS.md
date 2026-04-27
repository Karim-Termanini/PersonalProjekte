# Phase 3: `phase-3-dashboard-github-widgets` — Task Breakdown

> **Branch:** `phase-3-dashboard-github-widgets`
> **Goal:** Implement GitHub integration with authentication and dashboard widgets.
> **Agents:** 3 (Agent A, Agent B, Agent C)

---

## Agent Assignment Overview

| Agent | Focus Area | Deliverables |
|-------|-----------|--------------|
| **Agent A** | GitHub Authentication & API Client | PAT setup flow, secure token storage, async API client, rate limiting |
| **Agent B** | GitHub Widgets Implementation | Issues, PRs, Review Requested, Mentioned Me, Assigned to Me widgets |
| **Agent C** | GitHub Settings & UI Integration | Settings panel, widget gallery integration, error handling, UI polish |

---

## Agent A — GitHub Authentication & API Client

### Task A.1: GitHub Authentication Flow
**Priority:** High

Implement secure GitHub Personal Access Token (PAT) setup:
- `GitHubAuthDialog` for token input and validation
- Token storage using libsecret/Secret Service via Flatpak portal
- Token validation with GitHub API (`/user` endpoint)
- Permission checking (scopes: `repo`, `read:user`, `read:org`)
- Clear error messages for authentication failures

### Task A.2: Secure Token Storage
**Priority:** High
**Dependencies:** A.1

Implement secure credential management:
- Use `gi.repository.GLib.Keyfile` or `secret` service
- Encrypted storage in `~/.config/dev-home/github.ini`
- Token retrieval with proper error handling
- Token removal functionality

### Task A.3: Async GitHub API Client
**Priority:** High

Implement `src/core/github/client.py`:
- Async HTTP client using `aiohttp` or `httpx`
- Rate limit tracking and handling (X-RateLimit headers)
- Pagination support for all list endpoints
- Retry logic with exponential backoff
- Comprehensive error handling (network, auth, rate limits)

### Task A.4: Caching Layer
**Priority:** Medium
**Dependencies:** A.3

Implement caching to reduce API calls:
- In-memory cache with TTL (30 seconds for dynamic data, 5 minutes for static)
- Disk cache for offline access
- Cache invalidation on token change
- Cache statistics and management UI

---

## Agent B — GitHub Widgets Implementation

### Task B.1: GitHub Widget Base Class
**Priority:** High
**Dependencies:** Phase 2 A.1 (DashboardWidget base)

Create `src/ui/widgets/github_widget.py`:
- Extends `DashboardWidget` with GitHub-specific functionality
- Common patterns: loading states, error handling, refresh intervals
- Standardized GitHub data display patterns

### Task B.2: Issues Widget
**Priority:** High
**Dependencies:** B.1, A.3

Implement `src/ui/widgets/github_issues_widget.py`:
- Display user's open issues across all repositories
- Show issue title, repository, labels, assignees
- Time since creation/last update
- Click to open in browser
- Configurable filter (all repos, specific repos)
- Auto-refresh every 30 seconds

### Task B.3: Pull Requests Widget
**Priority:** High
**Dependencies:** B.1, A.3

Implement `src/ui/widgets/github_prs_widget.py`:
- Display user's open PRs
- Show PR title, repository, status (draft, ready, blocked)
- Review status indicators
- Merge status (mergeable, conflicts)
- Click to open in browser
- Auto-refresh every 30 seconds

### Task B.4: Review Requested Widget
**Priority:** Medium
**Dependencies:** B.1, A.3

Implement `src/ui/widgets/github_reviews_widget.py`:
- Display PRs awaiting user's review
- Repository and PR details
- Time since review requested
- Priority indicators (overdue, recent)
- Quick actions (open in browser, mark as reviewed)

### Task B.5: Mentioned Me & Assigned to Me Widgets
**Priority:** Medium
**Dependencies:** B.1, A.3

Implement two additional widgets:
- `github_mentions_widget.py`: Issues/PRs where user was mentioned
- `github_assigned_widget.py`: Issues assigned to user
- Show context snippets and repository details
- Quick filters by repository or label

---

## Agent C — GitHub Settings & UI Integration

### Task C.1: GitHub Settings Panel
**Priority:** High

Create `src/ui/settings/github.py`:
- Configure refresh interval (15s, 30s, 60s, 5min)
- Select which GitHub widgets to display
- Filter by repositories (include/exclude list)
- Notification preferences
- Cache management (clear cache button)
- API usage statistics display

### Task C.2: Widget Gallery Integration
**Priority:** Medium
**Dependencies:** Phase 2 A.3 (Widget Gallery)

Add GitHub widgets to widget gallery:
- Category: "GitHub"
- Search and filter for GitHub widgets
- Preview cards showing mock GitHub data
- Authentication requirement indicators

### Task C.3: Error Handling & Offline Support
**Priority:** High

Implement robust error handling:
- Network connectivity detection
- Graceful degradation when offline
- Cached data display with "stale" indicators
- User-friendly error messages with retry buttons
- Rate limit warnings and cooldown timers

### Task C.4: UI Polish & Performance
**Priority:** Medium

Optimize GitHub widgets:
- Efficient list rendering with `Gtk.ListBox` or custom widgets
- Lazy loading of avatars and images
- Smooth animations for data updates
- Memory management for large data sets
- Performance profiling and optimization

### Task C.5: Browser Integration
**Priority:** Low

Implement browser opening functionality:
- Use `Gtk.UriLauncher` for Flatpak portal compatibility
- Fallback to `webbrowser` module
- URL validation and sanitization
- History of opened links

---

## Phase 3 Acceptance Criteria (Global)

- [ ] GitHub authentication works correctly with secure token storage
- [ ] All 5 GitHub widgets display correct data from API
- [ ] Auto-refresh works without performance issues
- [ ] Rate limiting handled gracefully with user feedback
- [ ] Widgets handle offline/no network scenarios with cached data
- [ ] Click actions open correct URLs in browser
- [ ] Settings panel allows configuration of all GitHub features
- [ ] Widget gallery includes GitHub widgets with proper previews

---

## Technical Implementation Notes

### Dependencies to Add
```toml
# pyproject.toml
dependencies = [
    "aiohttp>=3.9.0",  # Async HTTP client
    "cachetools>=5.3.0",  # Caching utilities
    "python-dateutil>=2.8.0",  # Date parsing
]
```

### File Structure
```
src/
├── core/
│   ├── github/
│   │   ├── __init__.py
│   │   ├── client.py          # Async GitHub API client
│   │   ├── auth.py           # Authentication management
│   │   ├── cache.py          # Caching layer
│   │   └── models.py         # Data models (Issue, PR, etc.)
│   └── monitoring/
│       └── github_monitor.py  # Background GitHub data refresher
├── ui/
│   ├── widgets/
│   │   ├── github_widget.py           # Base class
│   │   ├── github_issues_widget.py    # Issues widget
│   │   ├── github_prs_widget.py       # PRs widget
│   │   ├── github_reviews_widget.py   # Review requested widget
│   │   ├── github_mentions_widget.py  # Mentioned me widget
│   │   └── github_assigned_widget.py  # Assigned to me widget
│   ├── dialogs/
│   │   └── github_auth.py    # Authentication dialog
│   └── settings/
│       └── github.py         # GitHub settings panel
└── dashboard/
    └── widgets/
        └── github.py         # GitHub widget registry
```

### Security Considerations
1. **Token Storage**: Use libsecret via Flatpak portal for secure storage
2. **Network Security**: HTTPS only, certificate validation
3. **Rate Limiting**: Respect GitHub API limits, implement backoff
4. **Data Privacy**: Clear cache on logout, minimal data retention

### Performance Targets
- API calls: < 1 request per widget per refresh interval
- Memory: < 50MB for GitHub data cache
- CPU: < 2% for background refresh operations
- Startup: Load cached data instantly, refresh in background

---

## Next Steps

1. **Agent A**: Start with authentication flow and API client
2. **Agent B**: Begin with base widget class and Issues widget
3. **Agent C**: Create settings panel and error handling
4. **Integration**: Connect all components and test end-to-end
5. **Polish**: Optimize performance and improve UX

---

*Phase 3 begins: 13 April 2026*