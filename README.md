# Streamlit Ticketing System (SQLite)

A simple ticketing system with a friendly Streamlit UI and SQLite persistence.
You can use the same `tickets.db` as the CLI version.

## Install & Run
```bash
# Run the ticketing system using Anaconda PowerShell Prompt

# (Optional) activate your Anaconda/conda environment
# conda activate myenv

# Install Streamlit (once)
pip install streamlit pandas

# Run the app (from the folder containing this file)
 ticketing_app.py and Use cmnd : streamlit run ticketing_app.py
```

## Features
- Create, list, filter, search tickets
- View & edit ticket fields (status, priority, assignee, tags, description)
- Add comments
- Export all tickets to CSV (download button)
- SQLite storage (`tickets.db`) — persists between runs

## Notes
- Valid statuses: `open`, `in_progress`, `closed`
- Priorities: `low`, `medium`, `high`, `urgent`
- Simple LIKE search across title/description/tags

### Using alongside the CLI
You can run the CLI (`ticketing_system.py`) and this Streamlit app against the same `tickets.db` file.
