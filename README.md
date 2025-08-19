Bathroom Status Dashboard

A simple Python/Flask web app that shows live bathroom availability based on a school bell schedule.Bathrooms are automatically marked CLOSED during the first and last 15 minutes of class, and OPEN during all other times (passing periods, breaks, lunch, and mid-class windows).

Designed to run on a Mac (or any computer with Python) and be displayed on a Chromebook or other device in kiosk mode.

**✨ Features**

Dashboard View (/)

Big live clock

Current status: ✅ OPEN / ❌ CLOSED

Next change time

Daily schedule of open windows

Admin View (/admin)

PIN-protected login

Edit the schedule in a web form (add, remove, or adjust periods)

Upload/Download schedule CSV for offline editing

Automatically persists to schedules.json

Offline friendly

No external dependencies beyond Flask

Data stored locally as JSON and CSV


**🚀 Getting Started**
1. Clone and set up

git clone https://github.com/yourusername/bathroom-status-dashboard.git

cd bathroom-status-dashboard

python3 -m venv .venv

source .venv/bin/activate

pip install flask
