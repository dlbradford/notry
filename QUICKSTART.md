# Notry Quick Start Guide

## Installation (One Time)

```bash
./install.sh
```

## Launch

```bash
./notry
```

## Essential Shortcuts

```
Enter    Edit/create note
Space    Mark note
a        Mark all
c        Clear marks
b        Browse marked
F2       Import files
F3       Export marked
j/k      Navigate
Ctrl+S   Save
Esc      Back
:help    Show full help
```

## Common Workflows

### Create Note
1. Type title
2. Press Enter
3. Type content
4. Ctrl+S to save

### Import Notes
1. F2
2. Navigate to files
3. Space to select
4. Enter to import

### Export Notes
1. Mark notes (Space)
2. F3 to export
3. Find in ~/Downloads/

### Browse & Edit
1. Mark notes (Space)
2. Press 'b'
3. Navigate with j/k
4. Enter to edit

## Database

Notes stored in: `notry.db` (current directory)

Use specific location:
```bash
./notry --db ~/my-notes.db
```

## Desktop Launcher

```bash
./create-desktop-launcher.sh
# Then double-click Notry.desktop
```

## Help

Type `:help` in the app for full command list.
