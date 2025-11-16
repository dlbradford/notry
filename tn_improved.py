#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
import sys
import textwrap
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

try:
    from textual.widgets import TextArea
    _HAS_TEXTAREA = True
except Exception:
    TextArea = None
    _HAS_TEXTAREA = False


# -------------------------
# Storage
# -------------------------
class NoteStore:
    def __init__(self, path: Path):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              body  TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              import_hash TEXT
            )
            """
        )
        self.conn.commit()
        
        # Migration: Add import_hash column if it doesn't exist
        cursor = self.conn.execute("PRAGMA table_info(notes)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'import_hash' not in columns:
            self.conn.execute("ALTER TABLE notes ADD COLUMN import_hash TEXT")
            self.conn.commit()
        
        # Add indexes
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_updated ON notes(updated_at DESC)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_import_hash ON notes(import_hash)")
        self.conn.commit()

    def count(self) -> int:
        (n,) = self.conn.execute("SELECT COUNT(*) FROM notes").fetchone()
        return int(n)

    def _compute_hash(self, title: str, body: str) -> str:
        content = f"{title}||{body}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def note_exists_by_hash(self, import_hash: str) -> bool:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM notes WHERE import_hash = ?",
            (import_hash,)
        ).fetchone()
        return row[0] > 0

    def upsert(self, title: str, body: str, note_id: Optional[int] = None, import_hash: Optional[str] = None) -> int:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if note_id is None:
            cur = self.conn.execute(
                "INSERT INTO notes (title, body, created_at, updated_at, import_hash) VALUES (?,?,?,?,?)",
                (title, body, now, now, import_hash),
            )
            self.conn.commit()
            return int(cur.lastrowid)
        else:
            self.conn.execute(
                "UPDATE notes SET title=?, body=?, updated_at=?, import_hash=? WHERE id=?",
                (title, body, now, import_hash, note_id),
            )
            self.conn.commit()
            return int(note_id)

    def get(self, note_id: int) -> Optional[Tuple[int, str, str, str, str]]:
        row = self.conn.execute(
            "SELECT id, title, body, created_at, updated_at FROM notes WHERE id=?",
            (note_id,),
        ).fetchone()
        return (int(row[0]), row[1], row[2], row[3], row[4]) if row else None

    def search(self, text: str, limit: int = 500) -> List[Tuple[int, str]]:
        if not text.strip():
            rows = self.conn.execute(
                """
                SELECT id, title || char(10) || body AS snip
                FROM notes
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            q = "%" + text.lower() + "%"
            rows = self.conn.execute(
                """
                SELECT id, title || char(10) || body AS snip
                FROM notes
                WHERE lower(title) LIKE ? OR lower(body) LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (q, q, limit),
            ).fetchall()
        return [(int(i), str(s)) for (i, s) in rows]

    def all(self) -> Iterable[Tuple[int, str, str, str, str]]:
        rows = self.conn.execute(
            "SELECT id, title, body, created_at, updated_at FROM notes ORDER BY updated_at DESC"
        ).fetchall()
        for r in rows:
            yield (int(r[0]), str(r[1]), str(r[2]), str(r[3]), str(r[4]))

    def export_separate_files(self, dir_path: Path, note_ids: Optional[List[int]] = None) -> int:
        dir_path.mkdir(parents=True, exist_ok=True)
        rows = (
            [self.get(nid) for nid in (note_ids or [])]
            if note_ids
            else list(self.all())
        )
        rows = [r for r in rows if r]
        n = 0
        for nid, title, body, created, updated in rows:
            safe = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()[:50] or f"note-{nid}"
            safe = safe.replace(" ", "-")
            p = dir_path / f"note-{nid}-{safe}.md"
            p.write_text(f"# {title}\n\n_Created: {created} · Updated: {updated}_\n\n{body}", encoding="utf-8")
            n += 1
        return n

    def import_text_file(self, path: Path) -> Tuple[int, int, Optional[int]]:
        """Import a text file. Returns (imported_count, skipped_count, note_id)"""
        content = path.read_text(encoding="utf-8", errors="replace")
        title = path.stem or "(untitled)"
        import_hash = self._compute_hash(title, content)
        if self.note_exists_by_hash(import_hash):
            return (0, 1, None)
        note_id = self.upsert(title, content, import_hash=import_hash)
        return (1, 0, note_id)

    def import_directory(self, dir_path: Path, extensions: tuple = (".md", ".markdown", ".txt")) -> Tuple[int, int, List[int]]:
        """Import all files from a directory. Returns (imported_count, skipped_count, [note_ids])"""
        imported = 0
        skipped = 0
        note_ids = []
        for p in sorted(dir_path.iterdir()):
            if p.is_file() and p.suffix.lower() in extensions:
                imp, skip, note_id = self.import_text_file(p)
                imported += imp
                skipped += skip
                if note_id is not None:
                    note_ids.append(note_id)
        return (imported, skipped, note_ids)

    def count_importable_files(self, dir_path: Path, extensions: tuple = (".md", ".markdown", ".txt")) -> int:
        if not dir_path.exists() or not dir_path.is_dir():
            return 0
        return sum(1 for p in dir_path.iterdir() if p.is_file() and p.suffix.lower() in extensions)

    def seed(self, n: int = 5) -> None:
        for i in range(n):
            title = f"Dummy note {i+1}"
            body = (
                "Created for testing Notry.\n"
                "This note contains keywords like alpha beta gamma delta.\n\n"
                "Use :help for commands."
            )
            self.upsert(title, body)

    def close(self):
        self.conn.close()


# -------------------------
# Confirmation Dialog
# -------------------------
class ConfirmDialog(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }
    #dialog {
        width: 60;
        height: auto;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    #dialog_message {
        width: 100%;
        height: auto;
        content-align: center middle;
        padding: 1 0;
    }
    #dialog_buttons {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1 0;
    }
    #dialog_buttons Button {
        margin: 0 1;
    }
    """
    
    def __init__(self, message: str, **kwargs):
        super().__init__(**kwargs)
        self.message = message
    
    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(self.message, id="dialog_message")
            with Horizontal(id="dialog_buttons"):
                yield Button("Yes", variant="primary", id="yes")
                yield Button("No", variant="default", id="no")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes":
            self.dismiss(True)
        else:
            self.dismiss(False)


# -------------------------
# Import Dialog with File Browser
# -------------------------
class FileItem(Static):
    """Represents a file in the import list"""
    file_path: Path
    is_selected: bool = False
    
    def __init__(self, file_path: Path, preview: str, **kwargs):
        super().__init__(**kwargs)
        self.file_path = file_path
        self.preview = preview
        self.is_selected = False
    
    def render(self) -> str:
        checkbox = "☑" if self.is_selected else "☐"
        return f"{checkbox} {self.file_path.name}\n  {self.preview}"
    
    def toggle_selection(self):
        self.is_selected = not self.is_selected
        self.refresh()


FileItem.DEFAULT_CSS = """
FileItem {
    height: auto;
    padding: 0 1;
    margin: 0 0 1 0;
    border: round $primary-background;
    background: $surface;
}

FileItem:hover {
    background: $boost;
}

FileItem:focus {
    border: round gold;
    background: $boost;
}
"""


class ImportDialog(ModalScreen[Optional[List[Path]]]):
    """Dialog for selecting files to import with directory navigation"""
    
    DEFAULT_CSS = """
    ImportDialog {
        align: center middle;
    }
    #import_container {
        width: 90%;
        height: 85%;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }
    #import_header {
        dock: top;
        height: 3;
        width: 100%;
        content-align: center middle;
        background: $primary-background;
        color: $text;
    }
    #path_display {
        dock: top;
        height: 3;
        width: 100%;
        padding: 0 2;
        background: $surface-lighten-1;
    }
    #file_list_container {
        height: 1fr;
        border: round $primary;
        padding: 1;
    }
    #button_bar {
        dock: bottom;
        height: 3;
        width: 100%;
        align: center middle;
    }
    #button_bar Button {
        margin: 0 1;
    }
    #stats_bar {
        dock: bottom;
        height: 1;
        width: 100%;
        padding: 0 2;
        background: $surface-lighten-1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("space", "toggle_selection", "Toggle", show=False),
        Binding("a", "select_all", "All", show=False),
        Binding("n", "select_none", "None", show=False),
        Binding("u,h", "go_up", "Up Dir", show=False),
        Binding("enter,l", "confirm_or_navigate", "Select/Open", show=False),
        Binding("j,down", "cursor_down", "Down", show=False),
        Binding("k,up", "cursor_up", "Up", show=False),
        Binding("g", "go_top", "Top", show=False),
        Binding("G", "go_bottom", "Bottom", show=False),
    ]
    
    def __init__(self, initial_path: Optional[Path] = None, extensions: tuple = (".md", ".txt"), **kwargs):
        super().__init__(**kwargs)
        self.current_path = initial_path or Path.home() / "Downloads"
        self.extensions = extensions
        self.file_items: List[FileItem] = []
        self.dir_items: List[Static] = []
    
    def compose(self) -> ComposeResult:
        from textual.containers import VerticalScroll
        
        with Vertical(id="import_container"):
            yield Static("Import Files - j/k=navigate, Space=toggle, a=all, n=none, h=parent, l/Enter=open, g/G=top/bottom", id="import_header")
            yield Static(f"📁 {self.current_path}", id="path_display")
            yield VerticalScroll(id="file_list_container")
            yield Static("0 files selected", id="stats_bar")
            with Horizontal(id="button_bar"):
                yield Button("Import Selected", variant="primary", id="import_btn")
                yield Button("Select All", variant="default", id="select_all_btn")
                yield Button("Select None", variant="default", id="select_none_btn")
                yield Button("Cancel", variant="default", id="cancel_btn")
    
    def on_mount(self) -> None:
        self.refresh_file_list()
    
    def refresh_file_list(self) -> None:
        """Refresh the file list for the current directory"""
        from textual.containers import VerticalScroll
        
        container = self.query_one("#file_list_container", VerticalScroll)
        container.remove_children()
        
        self.file_items.clear()
        self.dir_items.clear()
        
        # Update path display
        self.query_one("#path_display", Static).update(f"📁 {self.current_path}")
        
        if not self.current_path.exists() or not self.current_path.is_dir():
            container.mount(Static("Directory not found"))
            return
        
        try:
            # Add parent directory option if not at root
            if self.current_path != self.current_path.parent:
                parent_item = Static("📁 .. (parent directory)")
                parent_item.can_focus = True
                parent_item.add_class("directory-item")
                container.mount(parent_item)
                self.dir_items.append(parent_item)
            
            # List directories first
            dirs = sorted([d for d in self.current_path.iterdir() if d.is_dir()], key=lambda x: x.name.lower())
            for d in dirs:
                dir_item = Static(f"📁 {d.name}/")
                dir_item.can_focus = True
                dir_item.add_class("directory-item")
                dir_item.dir_path = d
                container.mount(dir_item)
                self.dir_items.append(dir_item)
            
            # List matching files
            files = sorted(
                [f for f in self.current_path.iterdir() 
                 if f.is_file() and f.suffix.lower() in self.extensions],
                key=lambda x: x.name.lower()
            )
            
            for f in files:
                preview = self._get_file_preview(f)
                file_item = FileItem(f, preview)
                file_item.can_focus = True
                container.mount(file_item)
                self.file_items.append(file_item)
            
            if not files and not dirs:
                container.mount(Static("No matching files or directories found"))
            
            # Focus first item
            if self.file_items:
                self.file_items[0].focus()
            elif self.dir_items:
                self.dir_items[0].focus()
                
        except PermissionError:
            container.mount(Static("Permission denied"))
        except Exception as e:
            container.mount(Static(f"Error: {e}"))
        
        self.update_stats()
    
    def _get_file_preview(self, path: Path, max_chars: int = 80) -> str:
        """Get a preview of the file content"""
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            # Get first non-empty line
            for line in content.split('\n'):
                line = line.strip()
                if line:
                    return line[:max_chars] + ("..." if len(line) > max_chars else "")
            return "(empty file)"
        except Exception:
            return "(unable to read)"
    
    def update_stats(self) -> None:
        """Update the statistics bar"""
        selected = sum(1 for item in self.file_items if item.is_selected)
        total = len(self.file_items)
        self.query_one("#stats_bar", Static).update(f"{selected} of {total} files selected")
    
    def action_toggle_selection(self) -> None:
        """Toggle selection of the focused file"""
        focused = self.focused
        if isinstance(focused, FileItem):
            focused.toggle_selection()
            self.update_stats()
            # Move to next item
            try:
                idx = self.file_items.index(focused)
                if idx < len(self.file_items) - 1:
                    self.file_items[idx + 1].focus()
            except (ValueError, IndexError):
                pass
    
    def action_select_all(self) -> None:
        """Select all files"""
        for item in self.file_items:
            item.is_selected = True
            item.refresh()
        self.update_stats()
    
    def action_select_none(self) -> None:
        """Deselect all files"""
        for item in self.file_items:
            item.is_selected = False
            item.refresh()
        self.update_stats()
    
    def action_go_up(self) -> None:
        """Navigate to parent directory"""
        if self.current_path != self.current_path.parent:
            self.current_path = self.current_path.parent
            self.refresh_file_list()
    
    def action_cursor_down(self) -> None:
        """Move focus down to next item (vim: j)"""
        focused = self.focused
        all_items = self.dir_items + self.file_items
        
        if not all_items:
            return
        
        if focused in all_items:
            idx = all_items.index(focused)
            if idx < len(all_items) - 1:
                all_items[idx + 1].focus()
                all_items[idx + 1].scroll_visible()
        elif all_items:
            # Nothing focused, focus first item
            all_items[0].focus()
    
    def action_cursor_up(self) -> None:
        """Move focus up to previous item (vim: k)"""
        focused = self.focused
        all_items = self.dir_items + self.file_items
        
        if not all_items:
            return
        
        if focused in all_items:
            idx = all_items.index(focused)
            if idx > 0:
                all_items[idx - 1].focus()
                all_items[idx - 1].scroll_visible()
        elif all_items:
            # Nothing focused, focus last item
            all_items[-1].focus()
    
    def action_go_top(self) -> None:
        """Jump to first item (vim: g)"""
        all_items = self.dir_items + self.file_items
        if all_items:
            all_items[0].focus()
            all_items[0].scroll_visible()
    
    def action_go_bottom(self) -> None:
        """Jump to last item (vim: G)"""
        all_items = self.dir_items + self.file_items
        if all_items:
            all_items[-1].focus()
            all_items[-1].scroll_visible()
    
    def action_confirm_or_navigate(self) -> None:
        """Navigate into directory or confirm selection"""
        focused = self.focused
        
        # Check if it's a directory item
        if hasattr(focused, 'add_class') and 'directory-item' in (focused.classes or set()):
            if hasattr(focused, 'dir_path'):
                # Navigate into directory
                self.current_path = focused.dir_path
                self.refresh_file_list()
            else:
                # Parent directory (..)
                self.action_go_up()
        elif isinstance(focused, FileItem):
            # Toggle selection of current file
            focused.toggle_selection()
            self.update_stats()
        else:
            # No specific item focused, try to import
            self.action_import_selected()
    
    def action_import_selected(self) -> None:
        """Import the selected files"""
        selected_files = [item.file_path for item in self.file_items if item.is_selected]
        self.dismiss(selected_files if selected_files else None)
    
    def action_cancel(self) -> None:
        """Cancel the import"""
        self.dismiss(None)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "import_btn":
            self.action_import_selected()
        elif button_id == "select_all_btn":
            self.action_select_all()
        elif button_id == "select_none_btn":
            self.action_select_none()
        elif button_id == "cancel_btn":
            self.action_cancel()


ImportDialog.DEFAULT_CSS += """
.directory-item {
    height: auto;
    padding: 0 1;
    margin: 0 0 1 0;
    background: $surface;
    color: $secondary;
}

.directory-item:hover {
    background: $boost;
}

.directory-item:focus {
    border: round gold;
    background: $boost;
}
"""


# -------------------------
# Results list
# -------------------------
class ResultsList(ListView):
    _id_to_note: dict[str, int]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._id_to_note = {}

    def clear_and_reset(self) -> None:
        self._id_to_note.clear()
        self.clear()

    def set_items(self, items: Sequence[Tuple[int, str]], marked: set[int], max_rows: int) -> None:
        self.clear_and_reset()
        for idx, (nid, snip) in enumerate(items[:max_rows]):
            mark = "✓" if nid in marked else " "
            line = snip.replace("\n", " ")[:200]
            label = Label(f"[{mark}]  #{nid}  {line}")
            wid = f"note-{nid}-{uuid.uuid4().hex[:6]}"
            self._id_to_note[wid] = nid
            self.append(ListItem(label, id=wid))
        if self.children:
            self.index = 0

    @property
    def current_note_id(self) -> Optional[int]:
        if self.index is None or not self.children:
            return None
        child = self.children[self.index]
        wid = child.id or ""
        return self._id_to_note.get(wid)


ResultsList.DEFAULT_CSS = """
ResultsList {
    height: 1fr;
    border: round cornflowerblue;
    padding: 0 1;
}
"""


# -------------------------
# Preview
# -------------------------
class Preview(Static):
    pass


Preview.DEFAULT_CSS = """
Preview {
    height: 1fr;
    border: round cornflowerblue;
    padding: 1 2;
}
"""


# -------------------------
# Browse Screen - Simple vertical layout, no absolute positioning
# -------------------------
class BrowseNoteCard(Static):
    note_id: int = 0
    
    def __init__(self, note_id: int, title: str, body: str, created: str, updated: str, **kwargs):
        super().__init__(**kwargs)
        self.note_id = note_id
        self.title_text = title
        self.body_text = body[:200]
        self.created = created
        self.updated = updated
    
    def render(self) -> str:
        return f"# {self.title_text}\n\n{self.body_text[:150]}..."
    
    async def on_click(self) -> None:
        """Handle click on card."""
        self.focus()
        screen = self.screen
        if isinstance(screen, BrowseScreen):
            # Update the current index to match this card
            try:
                screen.current_index = screen.cards.index(self)
            except:
                pass


BrowseNoteCard.DEFAULT_CSS = """
BrowseNoteCard {
    height: auto;
    min-height: 10;
    max-height: 15;
    border: round cornflowerblue;
    padding: 1;
    margin: 1;
    background: #1a1a1a;
}

BrowseNoteCard:focus {
    border: round gold;
    background: #252525;
}
"""


class BrowseScreen(ModalScreen[Optional[int]]):
    DEFAULT_CSS = """
    BrowseScreen {
        background: #0a0a0a;
    }
    #browse_container {
        width: 100%;
        height: auto;
    }
    #browse_header {
        dock: top;
        height: 3;
        background: #1a1a1a;
        color: #ffffff;
        border: round cornflowerblue;
        padding: 0 2;
        content-align: center middle;
    }
    """
    
    BINDINGS = [
        Binding("escape", "cancel", "Exit"),
        Binding("enter", "select", "Edit"),
        Binding("space,m", "toggle_mark", "Mark", show=False),
        Binding("a", "mark_all", "Mark All", show=False),
        Binding("c", "clear_marks", "Clear", show=False),
        Binding("f2", "import_notes", "Import", show=False),
        Binding("f3", "export_notes", "Export", show=False),
        Binding("j,down", "cursor_down", "Down", show=False),
        Binding("k,up", "cursor_up", "Up", show=False),
    ]
    
    def __init__(self, store: NoteStore, marked_set: set[int], **kwargs):
        super().__init__(**kwargs)
        self.store = store
        self.marked_set = marked_set  # Keep reference to the actual set
        self.marked_ids = sorted(marked_set)
        self.cards: List[BrowseNoteCard] = []
        self.current_index: int = 0
    
    def compose(self) -> ComposeResult:
        from textual.containers import VerticalScroll
        yield Static(
            f"BROWSE MODE - {len(self.marked_ids)} notes | Space=mark | a=mark all | c=clear | F3=export | Enter=edit | Esc=exit",
            id="browse_header"
        )
        yield VerticalScroll(id="browse_container")
    
    def on_mount(self) -> None:
        from textual.containers import VerticalScroll
        container = self.query_one("#browse_container", VerticalScroll)
        
        # Simply mount cards vertically - Textual handles layout automatically
        for nid in self.marked_ids:
            row = self.store.get(nid)
            if not row:
                continue
            _, title, body, created, updated = row
            
            card = BrowseNoteCard(nid, title, body, created, updated)
            card.can_focus = True
            container.mount(card)
            self.cards.append(card)
        
        if self.cards:
            self.current_index = 0
            self.cards[0].focus()
    
    def action_cursor_down(self) -> None:
        if self.cards and self.current_index < len(self.cards) - 1:
            self.current_index += 1
            self.cards[self.current_index].focus()
            self.cards[self.current_index].scroll_visible()
        elif self.cards:
            # Also handle case where focus is on a card but current_index is wrong
            focused = self.focused
            if focused and isinstance(focused, BrowseNoteCard):
                try:
                    idx = self.cards.index(focused)
                    if idx < len(self.cards) - 1:
                        self.current_index = idx + 1
                        self.cards[self.current_index].focus()
                        self.cards[self.current_index].scroll_visible()
                except ValueError:
                    pass
    
    def action_cursor_up(self) -> None:
        if self.cards and self.current_index > 0:
            self.current_index -= 1
            self.cards[self.current_index].focus()
            self.cards[self.current_index].scroll_visible()
        elif self.cards:
            # Also handle case where focus is on a card but current_index is wrong
            focused = self.focused
            if focused and isinstance(focused, BrowseNoteCard):
                try:
                    idx = self.cards.index(focused)
                    if idx > 0:
                        self.current_index = idx - 1
                        self.cards[self.current_index].focus()
                        self.cards[self.current_index].scroll_visible()
                except ValueError:
                    pass
    
    def action_cancel(self) -> None:
        self.dismiss(None)
    
    def action_select(self) -> None:
        """Edit the currently focused card."""
        # First try to get the focused widget
        focused = self.focused
        if focused and isinstance(focused, BrowseNoteCard):
            self.dismiss(focused.note_id)
            return
        
        # Fallback to current_index
        if self.cards and 0 <= self.current_index < len(self.cards):
            note_id = self.cards[self.current_index].note_id
            self.dismiss(note_id)
    
    def action_toggle_mark(self) -> None:
        """Toggle mark on the currently focused card."""
        focused = self.focused
        if not focused or not isinstance(focused, BrowseNoteCard):
            return
        
        note_id = focused.note_id
        if note_id in self.marked_set:
            self.marked_set.remove(note_id)
        else:
            self.marked_set.add(note_id)
        
        # Move to next card
        try:
            idx = self.cards.index(focused)
            if idx < len(self.cards) - 1:
                self.current_index = idx + 1
                self.cards[self.current_index].focus()
                self.cards[self.current_index].scroll_visible()
        except (ValueError, IndexError):
            pass
    
    def action_mark_all(self) -> None:
        """Mark all cards in browse mode."""
        count = len(self.cards)
        for card in self.cards:
            self.marked_set.add(card.note_id)
        self.app.notify(f"Marked all {count} notes in browse mode", severity="information")
    
    def action_clear_marks(self) -> None:
        """Clear all marks."""
        count = len(self.marked_set)
        self.marked_set.clear()
        self.app.notify(f"Cleared {count} marked notes", severity="information")
    
    def action_import_notes(self) -> None:
        """Import notes - delegates to the app."""
        app = self.app
        if hasattr(app, 'action_import_notes'):
            app.action_import_notes()
    
    def action_export_notes(self) -> None:
        """Export notes - delegates to the app."""
        app = self.app
        if hasattr(app, 'action_export_notes'):
            app.action_export_notes()
    
    def on_key(self, event) -> None:
        """Handle key events at screen level."""
        if event.key == "enter":
            # Check what has focus
            focused = self.focused
            if focused and isinstance(focused, BrowseNoteCard):
                # Update current_index to match focused card
                try:
                    self.current_index = self.cards.index(focused)
                except:
                    pass
                # Trigger edit
                self.dismiss(focused.note_id)
                event.prevent_default()
                event.stop()


# -------------------------
# Mode bar
# -------------------------
class ModeBar(Static):
    mode = reactive("SEARCH")
    rows = reactive(0)
    marked = reactive(0)
    message = reactive("")

    def update_info(self, mode: str, rows: int, marked: int, message: str = "") -> None:
        self.mode = mode
        self.rows = rows
        self.marked = marked
        self.message = message

    def render(self) -> str:
        left = f"MODE: {self.mode:<8} │ Rows: {self.rows:<3} │ Marked: {self.marked:<3}"
        right = " esc Back   f2 Import   f3 Export   Enter Edit   Space Mark   b Browse   Ctrl+S Save   :q Quit"
        return f"{left}\n{right}" if not self.message else f"{left} │ {self.message}\n{right}"


ModeBar.DEFAULT_CSS = """
ModeBar {
    height: 3;
    border: round cornflowerblue;
    padding: 0 1;
    color: white;
}
"""


# -------------------------
# App
# -------------------------
class NotryApp(App):
    CSS = """
    Screen { background: #111111; color: #DDDDDD; }
    #search { border: round #5e81ac; height: 3; padding: 0 1; color: white; background: #222222; }
    #main_horizontal { height: 1fr; }
    #results_container { width: 50%; }
    #content_container { width: 50%; }
    #results { height: 1fr; }
    #preview { height: 1fr; }
    #editor { height: 1fr; border: round cornflowerblue; }
    """

    BINDINGS = [
        Binding("escape", "mode_back", "Back"),
        Binding("enter", "open_or_edit", "Edit"),
        Binding("f2", "import_notes", "Import"),
        Binding("f3", "export_notes", "Export"),
        Binding("space,m", "toggle_mark", "Mark"),
        Binding("a", "mark_all", "Mark All", show=False),
        Binding("c", "clear_all_marks", "Clear All", show=False),
        Binding("j,down", "cursor_down", "Down", show=False),
        Binding("k,up", "cursor_up", "Up", show=False),
        Binding("ctrl+s", "save_edit", "Save", show=False),
        Binding("b", "toggle_browse_mode", "Browse", show=False),
    ]

    mode: str = "SEARCH"
    max_rows: int = 500
    marked: set[int]
    editing_note_id: Optional[int] = None
    original_body: str = ""

    def __init__(self, store: NoteStore):
        super().__init__()
        self.store = store
        self.matches: List[int] = []
        self.snips: List[str] = []
        self.marked = set()

    def _input(self) -> Input:
        return self.query_one("#search", Input)

    def _results(self) -> ResultsList:
        return self.query_one("#results", ResultsList)

    def _preview(self) -> Preview:
        return self.query_one("#preview", Preview)

    def _editor(self) -> Optional[TextArea]:
        if not _HAS_TEXTAREA:
            return None
        try:
            return self.query_one("#editor", TextArea)
        except:
            return None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Input(placeholder="Search or :command", id="search")
        with Horizontal(id="main_horizontal"):
            with Vertical(id="results_container"):
                yield ResultsList(id="results")
            with Vertical(id="content_container"):
                yield Preview(id="preview")
                if _HAS_TEXTAREA:
                    yield TextArea(id="editor")
        yield ModeBar(id="modebar")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "NotryApp"
        self.set_focus(self._input())
        if _HAS_TEXTAREA:
            ed = self._editor()
            if ed:
                ed.display = False
        self.refresh_search("")
        self.notify("Enter=edit | Space=mark | a=mark all | c=clear marks | :help for more", severity="information")

    def action_mode_back(self) -> None:
        if self.mode == "EDIT":
            if _HAS_TEXTAREA:
                ed = self._editor()
                if ed and ed.text != self.original_body:
                    self.notify("Unsaved changes! Ctrl+S to save, :q to quit without saving", severity="warning")
                    return
            
            self.mode = "SEARCH"
            self.editing_note_id = None
            self.original_body = ""
            if _HAS_TEXTAREA:
                ed = self._editor()
                if ed:
                    ed.display = False
            self._preview().display = True
            
            # Refresh the search to ensure list is up to date
            self.refresh_search(self._input().value)
            
            # Focus the input and refresh UI
            self.set_focus(self._input())
            self._refresh_status()
        else:
            self.mode = "SEARCH"
            self.set_focus(self._input())
            self._refresh_status()

    def action_open_or_edit(self) -> None:
        if self.mode != "SEARCH":
            return
        
        # Try to get the current note from the results list
        nid = self._results().current_note_id
        
        # Check which widget has focus to determine the behavior
        focused = self.focused
        results = self._results()
        
        # Check if focused widget is within the results list by walking up the tree
        is_in_results = False
        current = focused
        while current is not None:
            if current == results:
                is_in_results = True
                break
            current = current.parent
        
        if is_in_results and nid is not None:
            self._enter_edit(nid)
            return
        
        # If focus is on the input field (or anywhere else), use search box logic
        q = self._input().value.strip()
        if q:
            # Search for the text and edit first match, or create new note
            pairs = self.store.search(q, limit=1)
            if pairs:
                nid = pairs[0][0]
            else:
                nid = self.store.upsert(q, "")
                self.refresh_search(q)
            self._enter_edit(nid)
        else:
            # No search text, but try to edit the current highlighted note if any
            if nid is not None:
                self._enter_edit(nid)

    def action_toggle_mark(self) -> None:
        if self.mode == "EDIT":
            return
        nid = self._results().current_note_id
        if nid is None:
            return
        
        current_index = self._results().index
        
        if nid in self.marked:
            self.marked.remove(nid)
        else:
            self.marked.add(nid)
        
        self._refresh_results()
        
        if current_index is not None and self._results().children:
            next_index = min(current_index + 1, len(self._results().children) - 1)
            self._results().index = next_index
        
        self._refresh_preview()
        self._refresh_status()

    def action_clear_all_marks(self) -> None:
        """Clear all marked notes"""
        if self.mode == "EDIT":
            return
        
        if not self.marked:
            self.notify("No notes are marked", severity="information")
            return
        
        count = len(self.marked)
        self.marked.clear()
        self._refresh_results()
        self._refresh_preview()
        self._refresh_status()
        self.notify(f"Cleared {count} marked notes", severity="information")

    def action_mark_all(self) -> None:
        """Mark all notes in the current view/search results"""
        if self.mode == "EDIT":
            return
        
        if not self.matches:
            self.notify("No notes to mark", severity="information")
            return
        
        # Mark all notes in the current search results
        for note_id in self.matches:
            self.marked.add(note_id)
        
        self._refresh_results()
        self._refresh_preview()
        self._refresh_status()
        self.notify(f"Marked all {len(self.matches)} notes in current view", severity="information")

    def action_cursor_down(self) -> None:
        if self.mode == "EDIT":
            return
        self.set_focus(self._results())
        self._results().action_cursor_down()
        self._refresh_preview()

    def action_cursor_up(self) -> None:
        if self.mode == "EDIT":
            return
        self.set_focus(self._results())
        self._results().action_cursor_up()
        self._refresh_preview()

    def action_toggle_browse_mode(self) -> None:
        if self.mode == "EDIT":
            return
        if not self.marked:
            self.notify("No notes marked. Mark with Space first.", severity="warning")
            return
        self.run_worker(self._launch_browse_mode(), exclusive=True)
    
    async def _launch_browse_mode(self) -> None:
        result = await self.push_screen_wait(BrowseScreen(self.store, self.marked))
        # Refresh the list to show updated marks (browse mode modifies self.marked)
        self._refresh_results()
        self._refresh_preview()
        self._refresh_status()
        if result is not None:
            # Before entering edit mode, ensure we're in SEARCH mode
            if self.mode != "SEARCH":
                self.mode = "SEARCH"
            self._enter_edit(result)

    async def _do_import(self) -> None:
        """Launch the import dialog and import selected files"""
        downloads = Path.home() / "Downloads"
        
        # Launch the import dialog
        result = await self.push_screen_wait(ImportDialog(initial_path=downloads))
        
        if result is None or len(result) == 0:
            self.notify("Import cancelled", severity="information")
            return
        
        # Import the selected files
        try:
            imported = 0
            skipped = 0
            imported_note_ids = []
            
            for file_path in result:
                imp, skip, note_id = self.store.import_text_file(file_path)
                imported += imp
                skipped += skip
                if note_id is not None:
                    imported_note_ids.append(note_id)
            
            # Mark the imported notes so they're highlighted
            for note_id in imported_note_ids:
                self.marked.add(note_id)
            
            # Clear search to show all notes, highlighting the imported ones
            self._input().value = ""
            self.refresh_search("")
            
            if skipped > 0:
                self.notify(f"Imported {imported} new (marked with ✓), skipped {skipped} duplicates", severity="information")
            else:
                self.notify(f"Imported {imported} notes (marked with ✓)", severity="information")
            
        except Exception as e:
            self.notify(f"Import failed: {e}", severity="error")

    def action_import_notes(self) -> None:
        # Import should work even in EDIT mode
        self.run_worker(self._do_import(), exclusive=True)

    def action_export_notes(self) -> None:
        # Export should work even in EDIT mode
        
        # Require marked notes for export
        if not self.marked:
            self.notify("No notes marked for export. Mark notes with Space, or press 'a' to mark all", severity="warning")
            return
        
        downloads = Path.home() / "Downloads"
        if not downloads.exists():
            self.notify("~/Downloads not found", severity="warning")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = downloads / f"notry_export_{timestamp}"
        
        try:
            note_ids = list(self.marked)
            n = self.store.export_separate_files(export_dir, note_ids=note_ids)
            self.notify(f"Exported {n} marked notes → {export_dir}", severity="information")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")

    def action_save_edit(self) -> None:
        if self.mode != "EDIT":
            return
        if not _HAS_TEXTAREA:
            return
        ed = self._editor()
        nid = self.editing_note_id
        if nid is None or ed is None:
            return
        row = self.store.get(nid)
        if not row:
            return
        _, title, _, _, _ = row
        self.store.upsert(title, ed.text, note_id=nid)
        self.original_body = ed.text
        self.notify(f"Saved note #{nid}", severity="information")
        self.refresh_search(self._input().value)

    def on_input_changed(self, event: Input.Changed) -> None:
        text = event.value
        if text.startswith(":"):
            self._refresh_status(message=text)
            return
        if self.mode == "EDIT":
            return
        self.refresh_search(text)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if text.startswith(":"):
            self._run_command(text[1:].strip())
            return
        self.action_open_or_edit()
    
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle when Enter is pressed on a list item."""
        if self.mode != "SEARCH":
            return
        # Get the note ID from the selected item
        nid = self._results().current_note_id
        if nid is not None:
            self._enter_edit(nid)

    def _run_command(self, cmdline: str) -> None:
        tokens = cmdline.split()
        if not tokens:
            return
        cmd = tokens[0].lower()
        
        if cmd in ("quit", "q"):
            if self.mode == "EDIT":
                self.mode = "SEARCH"
                self.editing_note_id = None
                self.original_body = ""
                if _HAS_TEXTAREA:
                    ed = self._editor()
                    if ed:
                        ed.display = False
                self._preview().display = True
                self.set_focus(self._input())
                self._refresh_status()
                self.notify("Quit without saving", severity="information")
            return

        if cmd == "help":
            help_text = """
            Enter=edit | Space=mark | a=mark all | c=clear marks | b=browse marked
            F2=import | F3=export | Ctrl+S=save | Esc=back | :q=quit without save
            """
            self.notify(help_text.strip(), severity="information", timeout=10)
            return

        self.notify(f"Unknown command: {cmd}", severity="warning")

    def refresh_search(self, text: str) -> None:
        pairs = self.store.search(text, limit=self.max_rows)
        self.matches = [nid for nid, _ in pairs]
        self.snips = [snip for _, snip in pairs]
        self._refresh_results()
        self._refresh_preview()
        self._refresh_status()

    def _refresh_results(self) -> None:
        items = list(zip(self.matches, self.snips))
        self._results().set_items(items, self.marked, self.max_rows)

    def _refresh_preview(self) -> None:
        if self.mode == "EDIT":
            return
        if not self.matches:
            self._preview().update("No notes.")
            return
        nid = self._results().current_note_id or self.matches[0]
        row = self.store.get(nid)
        if not row:
            self._preview().update("(missing)")
            return
        _, title, body, created, updated = row
        self._preview().update(f"# {title}\n\n_Created: {created} · Updated: {updated}_\n\n{body}")

    def _refresh_status(self, message: str = "") -> None:
        mb: ModeBar = self.query_one("#modebar", ModeBar)
        mb.update_info(self.mode, rows=len(self.matches), marked=len(self.marked), message=message)

    def _enter_edit(self, nid: int) -> None:
        row = self.store.get(nid)
        if not row:
            self.notify(f"Note {nid} not found", severity="warning")
            return
        _, title, body, _, _ = row
        
        if not _HAS_TEXTAREA:
            self.notify("TextArea not available", severity="error")
            return
        
        ed = self._editor()
        if not ed:
            self.notify("Editor not available", severity="error")
            return
        
        self.mode = "EDIT"
        self.editing_note_id = nid
        self.original_body = body
        self._preview().display = False
        
        ed.display = True
        ed.text = body
        ed.focus()
        self._refresh_status(message=f"Editing #{nid}: {title}")
        self.notify(f"EDIT mode - {title} (Ctrl+S=save, Esc=back, :q=quit)", severity="information")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Notry TUI notes")
    p.add_argument("--db", type=Path, default=Path("notry.db"))
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--reset", action="store_true")
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    db_path: Path = args.db

    if args.reset and db_path.exists():
        try:
            db_path.unlink()
            print(f"Deleted DB: {db_path}")
        except Exception as e:
            print(f"Failed to delete: {e}", file=sys.stderr)
            return 2

    store = NoteStore(db_path)
    if args.seed > 0 and store.count() == 0:
        store.seed(args.seed)
        print(f"Created {args.seed} notes.")

    app = NotryApp(store)
    app.run()
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
