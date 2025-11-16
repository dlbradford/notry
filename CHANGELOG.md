# Notry Changelog

## Version 1.0.0 - November 2024

### Features
- Full-text search across note titles and content
- Create, edit, and save notes with keyboard shortcuts
- Mark notes for batch operations (mark/unmark/clear all)
- Browse mode with card-based view for reviewing marked notes
- Import dialog with filesystem navigation
  - Browse directories
  - Preview file contents
  - Select multiple files
  - Auto-mark imported notes
- Export marked notes as markdown files
- SQLite database with automatic duplicate detection
- Command-line interface with vim-style navigation (j/k)
- Textual-based TUI with responsive design

### Bug Fixes
- ✅ Fixed browse mode marks not persisting when returning to main screen
- ✅ Fixed database persistence between sessions
- ✅ Fixed import dialog showing proper file previews
- ✅ Fixed export requiring marks (no accidental export all)
- ✅ Fixed list selection with j/k/arrow keys
- ✅ Fixed Enter key working in both search mode and list mode
- ✅ Fixed browse mode header visibility
- ✅ Fixed F2/F3 working in all modes including browse
- ✅ Fixed mark all functionality in browse mode
- ✅ Fixed Python version detection and user site-packages path

### Known Issues
- GUI launcher (notry-gui) may not work from file manager on GNOME
  - **Workaround**: Use create-desktop-launcher.sh to create Notry.desktop
- Requires Python 3.7+ (configured for Python 3.14 by default)
- Only supports .txt and .md file import

### Technical Details
- Database: SQLite with automatic commits
- Import hash: SHA256 for duplicate detection
- Export format: Markdown with metadata
- Storage: Local file system
- Dependencies: textual>=0.47.0

### Keyboard Shortcuts
- Main: Enter, Space, a, c, b, j/k, F2, F3, Esc
- Edit: Ctrl+S, Esc, :q
- Browse: Enter, Space, a, c, F3, j/k, Esc
- Import: Space, a, n, u, Enter, Esc

### Command Line
- `--db PATH` - Use custom database location
- `--seed N` - Create N test notes
- `--reset` - Delete database and start fresh

### Files Structure
```
notry-final-package/
├── notry                      - Main launcher
├── notry-gui                  - GUI wrapper
├── tn_improved.py             - Source code (1406 lines)
├── install.sh                 - Setup script
├── create-desktop-launcher.sh - Desktop file creator
├── requirements.txt           - Dependencies
├── README.md                  - Full documentation
├── QUICKSTART.md              - Quick reference
└── CHANGELOG.md               - This file
```

### Development Notes
- Built with Textual framework
- Single-file application (tn_improved.py)
- No external configuration files needed
- Database auto-creates on first run
- Cross-platform compatible (Linux, macOS)

### Credits
Developed collaboratively with Claude (Anthropic) over multiple iterations to address user feedback and bug reports.
