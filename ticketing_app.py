#!/usr/bin/env python3
# ticketing_app.py
# Run with: streamlit run ticketing_app.py
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
import pandas as pd
import io

import streamlit as st

DB_FILE = "tickets.db"
STATUSES = ("open", "in_progress", "closed")
PRIORITIES = ("low", "medium", "high", "urgent")


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


@dataclass
class Ticket:
    id: Optional[int]
    title: str
    description: str
    status: str = "open"
    priority: str = "medium"
    requester: Optional[str] = None
    assignee: Optional[str] = None
    tags: Optional[str] = None  # comma-separated string
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TicketingSystem:
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        # check_same_thread False to allow Streamlit reruns to reuse connection safely
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','in_progress','closed')),
                priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
                requester TEXT,
                assignee TEXT,
                tags TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                author TEXT,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
            CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);
            CREATE INDEX IF NOT EXISTS idx_tickets_assignee ON tickets(assignee);
            """
        )
        self.conn.commit()

    # CRUD
    def create_ticket(self, t: Ticket) -> int:
        created = now_iso()
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO tickets (title, description, status, priority, requester, assignee, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (t.title, t.description, t.status, t.priority, t.requester, t.assignee, t.tags, created, created),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_ticket(self, ticket_id: int) -> Optional[Ticket]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = cur.fetchone()
        if not row:
            return None
        return Ticket(
            id=row["id"],
            title=row["title"],
            description=row["description"] or "",
            status=row["status"],
            priority=row["priority"],
            requester=row["requester"],
            assignee=row["assignee"],
            tags=row["tags"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_tickets(self, filters: Dict[str, Any] = None) -> List[sqlite3.Row]:
        filters = filters or {}
        clauses = []
        params: List[Any] = []

        if filters.get("status"):
            clauses.append("status = ?")
            params.append(filters["status"])
        if filters.get("priority"):
            clauses.append("priority = ?")
            params.append(filters["priority"])
        if filters.get("assignee"):
            clauses.append("assignee = ?")
            params.append(filters["assignee"])

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""SELECT id, title, status, priority, assignee, requester, tags, created_at, updated_at
                  FROM tickets {where_sql}
                  ORDER BY
                    CASE status
                      WHEN 'open' THEN 0
                      WHEN 'in_progress' THEN 1
                      ELSE 2
                    END,
                    CASE priority
                      WHEN 'urgent' THEN 0
                      WHEN 'high' THEN 1
                      WHEN 'medium' THEN 2
                      ELSE 3
                    END,
                    created_at DESC;"""
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    def update_ticket(self, ticket_id: int, updates: Dict[str, Any]) -> bool:
        if not updates:
            return False
        columns = []
        params: List[Any] = []
        for k, v in updates.items():
            columns.append(f"{k} = ?")
            params.append(v)
        columns.append("updated_at = ?")
        params.append(now_iso())
        params.append(ticket_id)
        sql = f"UPDATE tickets SET {', '.join(columns)} WHERE id = ?"
        cur = self.conn.cursor()
        cur.execute(sql, params)
        self.conn.commit()
        return cur.rowcount > 0

    def add_comment(self, ticket_id: int, author: Optional[str], body: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO comments (ticket_id, author, body, created_at) VALUES (?, ?, ?, ?)",
            (ticket_id, author, body, now_iso()),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_comments(self, ticket_id: int) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, author, body, created_at FROM comments WHERE ticket_id = ? ORDER BY id ASC",
            (ticket_id,),
        )
        return cur.fetchall()

    def search(self, query: str) -> List[sqlite3.Row]:
        like = f"%{query}%"
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, title, status, priority, assignee, requester, tags, created_at, updated_at
            FROM tickets
            WHERE title LIKE ? OR description LIKE ? OR tags LIKE ?
            ORDER BY updated_at DESC
            """,
            (like, like, like),
        )
        return cur.fetchall()

    def export_csv_bytes(self) -> bytes:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM tickets ORDER BY id ASC")
        rows = [dict(r) for r in cur.fetchall()]
        df = pd.DataFrame(rows)
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        return buf.getvalue().encode("utf-8")


# ---------------- Streamlit UI ---------------- #
st.set_page_config(page_title="Ticketing System", layout="wide")
st.title("🎫 Ticketing System (SQLite + Streamlit)")

# Keep a single TicketingSystem instance across reruns
if "ts" not in st.session_state:
    st.session_state.ts = TicketingSystem(DB_FILE)

ts: TicketingSystem = st.session_state.ts

# Sidebar: Create ticket + filters + search
with st.sidebar:
    st.header("New Ticket")
    with st.form("create_ticket_form", clear_on_submit=True):
        title = st.text_input("Title", "")
        description = st.text_area("Description", "")
        requester = st.text_input("Requester (name/email)", "")
        assignee = st.text_input("Assignee (optional)", "")
        tags = st.text_input("Tags (comma-separated)", "")
        priority = st.selectbox("Priority", PRIORITIES, index=1)
        status = st.selectbox("Status", STATUSES, index=0)
        submitted = st.form_submit_button("Create Ticket")
        if submitted:
            if not title.strip():
                st.warning("Title is required.")
            else:
                t = Ticket(
                    id=None,
                    title=title.strip(),
                    description=description.strip(),
                    status=status,
                    priority=priority,
                    requester=requester.strip() or None,
                    assignee=assignee.strip() or None,
                    tags=tags.strip() or None,
                )
                new_id = ts.create_ticket(t)
                st.success(f"Created ticket #{new_id}")

    st.header("Filters")
    f_status = st.selectbox("Status filter", options=("",) + STATUSES, index=0, help="Leave blank for all")
    f_priority = st.selectbox("Priority filter", options=("",) + PRIORITIES, index=0, help="Leave blank for all")
    f_assignee = st.text_input("Assignee filter", "")

    st.header("Search")
    q = st.text_input("Title/Description/Tags", "")

# Main area: tabs
tab_list, tab_detail, tab_export = st.tabs(["📋 Tickets", "🔎 View / Edit", "⬇️ Export"])

with tab_list:
    filters = {
        "status": f_status or None,
        "priority": f_priority or None,
        "assignee": f_assignee.strip() or None,
    }
    rows = ts.search(q.strip()) if q.strip() else ts.list_tickets(filters)
    df = pd.DataFrame(rows, columns=["id","title","status","priority","assignee","requester","tags","created_at","updated_at"]) if rows else pd.DataFrame(columns=["id","title","status","priority","assignee","requester","tags","created_at","updated_at"])
    st.subheader("Tickets")
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Selection helper
    if not df.empty:
        st.divider()
        sel_id = st.selectbox("Select a ticket to view/edit", options=df["id"].tolist())
        st.session_state["selected_ticket_id"] = sel_id
        st.info(f"Selected ticket #{sel_id}. Go to the **View / Edit** tab.")

with tab_detail:
    sel_id = st.session_state.get("selected_ticket_id")
    if not sel_id:
        st.caption("Pick a ticket in the Tickets tab to view it here.")
    else:
        ticket = ts.get_ticket(int(sel_id))
        if not ticket:
            st.error("Ticket not found.")
        else:
            st.subheader(f"Ticket #{ticket.id} — {ticket.title}")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Status", ticket.status)
            with col2:
                st.metric("Priority", ticket.priority)
            with col3:
                st.metric("Assignee", ticket.assignee or "-")

            with st.expander("Details", expanded=True):
                st.write(f"**Requester:** {ticket.requester or '-'}")
                st.write(f"**Tags:** {ticket.tags or '-'}")
                st.write(f"**Created:** {ticket.created_at}")
                st.write(f"**Updated:** {ticket.updated_at}")
                st.write("**Description:**")
                st.write(ticket.description or "-")

            st.markdown("---")
            st.subheader("Edit Ticket")
            with st.form(f"edit_ticket_{ticket.id}"):
                new_title = st.text_input("Title", value=ticket.title)
                new_desc = st.text_area("Description", value=ticket.description)
                new_priority = st.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(ticket.priority))
                new_tags = st.text_input("Tags", value=ticket.tags or "")
                new_assignee = st.text_input("Assignee", value=ticket.assignee or "")
                new_status = st.selectbox("Status", STATUSES, index=STATUSES.index(ticket.status))
                do_update = st.form_submit_button("Save Changes")
                if do_update:
                    updates: Dict[str, Any] = {}
                    if new_title != ticket.title:
                        updates["title"] = new_title.strip()
                    if new_desc != ticket.description:
                        updates["description"] = new_desc.strip()
                    if new_priority != ticket.priority:
                        updates["priority"] = new_priority
                    if (new_tags or None) != (ticket.tags or None):
                        updates["tags"] = new_tags.strip() or None
                    if (new_assignee or None) != (ticket.assignee or None):
                        updates["assignee"] = new_assignee.strip() or None
                    if new_status != ticket.status:
                        updates["status"] = new_status
                    if updates:
                        ok = ts.update_ticket(ticket.id, updates)
                        if ok:
                            st.success("Ticket updated.")
                        else:
                            st.warning("No changes saved.")
                    else:
                        st.info("Nothing to change.")
                    st.experimental_rerun()

            st.subheader("Comments")
            comments = ts.get_comments(ticket.id)
            if comments:
                for c in comments:
                    who = c["author"] or "Anonymous"
                    st.markdown(f"- **{who}** · _{c['created_at']}_  \n{c['body']}")
            else:
                st.caption("No comments yet.")

            with st.form(f"add_comment_{ticket.id}", clear_on_submit=True):
                c_author = st.text_input("Your name (optional)")
                c_body = st.text_area("Comment")
                add_c = st.form_submit_button("Add Comment")
                if add_c:
                    if not c_body.strip():
                        st.warning("Comment cannot be empty.")
                    else:
                        ts.add_comment(ticket.id, c_author.strip() or None, c_body.strip())
                        st.success("Comment added.")
                        st.experimental_rerun()

with tab_export:
    st.subheader("Export Tickets to CSV")
    csv_bytes = ts.export_csv_bytes()
    st.download_button(
        "Download CSV",
        data=csv_bytes,
        file_name="tickets_export.csv",
        mime="text/csv",
        help="Exports all tickets from the database."
    )

    st.markdown("Tip: You can keep using the same `tickets.db` file across the CLI and Streamlit apps.")
