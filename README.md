# Notry - Terminal Notes Application

A powerful, keyboard-driven note-taking application for the terminal.

## Quick Start

```bash
./install.sh    # One-time setup
./notry         # Launch the app
```

## Installation

### 1. Extract Files

Extract the zip to a directory of your choice.

### 2. Install Textual

**Automatic:**
```bash
./install.sh
```

**Manual:**
```bash
python3.14 -m pip install --user textual
```

### 3. Run

**Command Line:**
```bash
./notry
```

**GUI/File Manager:**
```bash
./create-desktop-launcher.sh    # Creates Notry.desktop
# Then double-click Notry.desktop
```

## Features

### Core Features
- ✅ Full-text search across titles and content
- ✅ Create, edit, save notes
- ✅ Mark notes for batch operations
- ✅ Browse marked notes in card view
- ✅ Import .txt and .md files from filesystem
- ✅ Export marked notes as markdown
- ✅ SQLite database with duplicate detection
- ✅ Keyboard-driven interface

### Recent Fixes
- ✅ Browse mode marks now persist
- ✅ Database saves properly between sessions
- ✅ Python 3.14 explicitly configured
- ✅ Desktop launcher creation script

## Keyboard Shortcuts

### Main View (SEARCH Mode)
| Key | Action |
|-----|--------|
| `Enter` | Edit selected note or create new from search text |
| `Space` | Toggle mark on current note (and move to next) |
| `a` | Mark all notes in current view |
| `c` | Clear all marks |
| `b` | Browse marked notes in card view |
| `j` / `↓` | Move down in list |
| `k` / `↑` | Move up in list |
| `F2` | Open import dialog |
| `F3` | Export marked notes |
| `Esc` | Return from edit mode |
| `:help` | Show help |
| `:q` | Quit without saving (in edit mode) |

### Browse Mode
| Key | Action |
|-----|--------|
| `Enter` | Edit selected note |
| `Space` | Toggle mark on current note |
| `a` | Mark all notes in browse view |
| `c` | Clear all marks |
| `F3` | Export marked notes (no need to exit!) |
| `j` / `↓` | Move to next card |
| `k` / `↑` | Move to previous card |
| `Esc` | Exit browse mode |

### Edit Mode
| Key | Action |
|-----|--------|
| `Ctrl+S` | Save changes |
| `Esc` | Return to list (prompts if unsaved) |
| `:q` | Quit without saving |

### Import Dialog
| Key | Action |
|-----|--------|
| `Space` | Toggle selection on file |
| `a` | Select all files |
| `n` | Deselect all files |
| `u` | Go up to parent directory |
| `Enter` | Navigate directory or import selected |
| `Esc` | Cancel import |

## Usage Examples

### Basic Note Taking
1. Launch `./notry`
2. Type a title or search text
3. Press `Enter` to create/edit
4. Type your note
5. Press `Ctrl+S` to save
6. Press `Esc` to return

### Importing Notes
1. Press `F2`
2. Navigate with arrow keys or `j/k`
3. Press `Enter` to open directories
4. Press `Space` to select files
5. Press `a` to select all
6. Press `Enter` to import
7. Imported notes are auto-marked with ✓

### Exporting Notes
1. Mark notes you want (press `Space` on each)
2. Or press `a` to mark all
3. Press `F3` to export
4. Files saved to `~/Downloads/notry_export_TIMESTAMP/`

### Reviewing Notes
1. Mark several notes with `Space`
2. Press `b` to browse
3. Navigate with `j/k`
4. Press `Space` to toggle marks
5. Press `a` to mark all remaining
6. Press `F3` to export directly
7. Press `Esc` when done

### Searching
- **Show all**: Clear the search box
- **Filter**: Type keywords
- **Mark matches**: Press `a` after searching
- **Search results**: Only matches shown

## Command Line Options

```bash
./notry --help              # Show all options
./notry --db ~/notes.db     # Use different database
./notry --seed 10           # Create 10 test notes
./notry --reset             # Delete database (CAREFUL!)
```

## File Locations

### Database
By default: `notry.db` in current directory

Use a specific location:
```bash
./notry --db ~/Documents/my-notes.db
```

### Exports
Default location: `~/Downloads/notry_export_TIMESTAMP/`

### Import Source
Configurable in import dialog (browse anywhere)

## Configuration

### Using Different Python Version

Edit the first line of `notry`:
```python
#!/usr/bin/env python3.14
```

Change to your Python version:
```python
#!/usr/bin/env python3.12
```

Then install textual for that version:
```bash
python3.12 -m pip install --user textual
```

### Desktop Integration

**Create launcher:**
```bash
./create-desktop-launcher.sh
```

**Add to desktop:**
```bash
cp Notry.desktop ~/Desktop/
```

**Add to applications menu:**
```bash
cp Notry.desktop ~/.local/share/applications/
```

## Files Included

| File | Purpose |
|------|---------|
| `notry` | Main launcher executable |
| `notry-gui` | GUI wrapper (opens terminal) |
| `tn_improved.py` | Application source code |
| `install.sh` | Setup/installation script |
| `create-desktop-launcher.sh` | Desktop file generator |
| `requirements.txt` | Python dependencies |
| `README.md` | This file |
| `QUICKSTART.md` | Quick reference guide |
| `CHANGELOG.md` | Version history |

## Troubleshooting

### "No module named 'textual'"

**Solution:**
```bash
python3.14 -m pip install --user textual
```

Or edit `notry` to use your Python version.

### GUI launcher opens in browser/editor

**Cause:** File not executable or GNOME opens scripts in editor

**Solutions:**

1. Make executable:
```bash
chmod +x notry-gui
```

2. Use desktop file instead:
```bash
./create-desktop-launcher.sh
# Then double-click Notry.desktop
```

3. Change GNOME settings:
```bash
gsettings set org.gnome.nautilus.preferences executable-text-activation 'launch'
```

### Notes don't persist between sessions

**Check:**
1. Are you running from the same directory?
2. Database location: `ls -la notry.db`
3. Use explicit path: `./notry --db ~/mynotes.db`

**Each directory has its own database unless you specify `--db`**

### Import fails / no files shown

**Check:**
1. File extensions must be `.txt` or `.md`
2. Files must be readable
3. Navigate to correct directory in import dialog

### Browse mode marks don't persist

**This is fixed in the latest version.**

If still happening:
1. Make sure you have the latest `tn_improved.py`
2. Press `Esc` to exit browse mode (triggers refresh)

## Tips & Tricks

1. **Quick note creation**: Type title, press Enter - no search needed
2. **Batch operations**: Mark multiple notes, browse them all at once
3. **Keyboard efficiency**: Learn `j/k` navigation - much faster
4. **Import workflow**: Mark all after import to review new notes
5. **Search then export**: Search keyword, press `a`, then `F3`
6. **Duplicate prevention**: Same file won't import twice (hash-based)

## Support

- Type `:help` in the app for commands
- Read source: `tn_improved.py` (well commented)
- All functionality is self-contained

## Version

- **Application**: Notry v1.0.0
- **Last Updated**: November 2025
- **Python Requirement**: 3.7+ (configured for 3.14)
- **Dependencies**: textual

## License

Free for personal and educational use.

## Credits

Developed collaboratively with Claude (Anthropic).
