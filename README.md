Bathroom Status Dashboard

This project is a lightweight, offline-friendly web dashboard for schools to display bathroom availability in real time. Built with Flask, it shows a live clock, current status (OPEN/CLOSED), next change time, and daily open windows. An admin panel (PIN-protected) allows schedules to be edited directly in the browser or uploaded via CSV, making it simple to adapt to bell changes without touching code.

Bathrooms are automatically marked CLOSED during the first and last 15 minutes of class, and OPEN during all other times (passing periods, breaks, lunch, and mid-class windows).

Designed to run on a Mac (or any computer with Python) and displayed on a Chromebook in kiosk mode for students and staff.

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
