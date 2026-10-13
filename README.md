# Vehicle Parking Management System (ParkEasy)

A multi-user 4-wheeler vehicle parking and expert fleet management web application built with Flask, SQLite, and Bootstrap.

## Features

- **Multi-Role Access**: Administrator and User roles with secure authentication and session management.
- **Admin Dashboard**:
  - Real-time overview of total parking lots, available spots, and active reservations.
  - Create, view, edit, and manage parking lots and parking spots.
  - Driver & Valet Management: Add, edit, and assign drivers.
  - View all user bookings, parking histories, and driver reservations.
- **User Dashboard**:
  - Live search and real-time spot availability checking.
  - Instant spot booking with cost calculation based on duration.
  - Release parking spot with automated billing calculation.
  - Valet driver booking for assisted vehicle parking.
  - Past booking history with timestamps and cost breakdowns.
- **Vercel Serverless Ready**:
  - Compatible with Vercel Python Serverless Functions via WSGI entrypoint (`api/index.py`).
  - Automatic ephemeral SQLite `/tmp` synchronization for read/write capability in serverless environments.

## Project Structure

```
├── app.py                 # Core Flask application and route definitions
├── controllers/           # Modular request controllers (admin & user)
│   ├── admin_controller.py
│   └── user_controller.py
├── models/                # Database models and table initializers
│   └── init_db.py
├── static/                # Static assets (CSS stylesheets, JS, icons)
│   └── css/
│       └── style.css
├── templates/             # Jinja2 HTML templates
│   ├── admin_*.html
│   ├── home.html
│   ├── login.html
│   ├── register.html
│   └── user_*.html
├── api/                   # Vercel serverless function entrypoint
│   └── index.py
├── parking.db             # Pre-seeded SQLite database
├── requirements.txt       # Python dependencies
├── vercel.json            # Vercel deployment and routing configuration
└── README.md
```

## Running Locally

1. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Start the application:
   ```bash
   python app.py
   ```

4. Open `http://127.0.0.1:5000` in your web browser.

## Deployment on Vercel

The project is configured for 1-click deployment on Vercel:
- **Framework Preset**: Other
- **Root Directory**: `./`
- **Output Directory**: Automatically handled by `vercel.json` rewrites and `api/index.py`.
