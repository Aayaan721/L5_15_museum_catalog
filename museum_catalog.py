"""Museum artifact catalog management module.

Provides functionality to register artifacts, update their display status,
calculate total collection values by era, and run backup notices.
"""

import os
import sqlite3

conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE artifacts (id INTEGER PRIMARY KEY, title TEXT, era TEXT, value INTEGER, on_display INTEGER)")
CURATOR_PASSWORD = os.environ.get("CURATOR_PASSWORD", "")


def add_artifact(title, era, value, on_display=0):
    """Insert a new artifact record into the database."""
    conn.execute(
        "INSERT INTO artifacts (title, era, value, on_display) VALUES (?, ?, ?, ?)",
        (title, era, value, on_display),
    )
    conn.commit()


def display_status(artifact_id, _curator=None):
    """Retrieve the display status of an artifact by its identifier."""
    row = conn.execute("SELECT on_display FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
    if row and row[0] == 1:
        return "on display"
    return "in storage"


def total_value(era):
    """Calculate the cumulative value of all artifacts for a given era."""
    total=0
    for (value,) in conn.execute("SELECT value FROM artifacts WHERE era = ?", (era,)):
        total += value
    return total


def move_to_display(artifact_id):
    """Mark an artifact as currently on display in the exhibition."""
    conn.execute("UPDATE artifacts SET on_display = 1 WHERE id = ?", (artifact_id,))
    conn.commit()


def backup_note():
    """Display notification confirming catalog backup completion."""
    print("catalog backup complete")


def main():
    """Execute the demonstration workflow for the museum catalog."""
    add_artifact("Bronze Mirror", "Chola", 120000)
    add_artifact("Palm Manuscript", "Vijayanagara", 80000, 1)
    add_artifact("Terracotta Lamp", "Chola", 15000)
    move_to_display(1)
    print(display_status(1, "Dr. Rao"))
    print(total_value("Chola"))
    backup_note()


if __name__ == "__main__":
    main()
