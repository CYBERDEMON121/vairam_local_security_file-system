# Vairam — SecureCloud

Vairam is a local Flask file-storage prototype with account management, optional TOTP-based two-factor authentication, and experimental biometric features. Files and metadata are stored locally rather than in an external cloud service.

> **Project status:** educational prototype. This application is not production-ready and should not be used to store sensitive data as-is.

## Features

- User registration and login with securely hashed passwords
- TOTP two-factor authentication using an authenticator app
- QR-code enrollment for authenticator applications
- Local file upload, download, deletion, and storage-usage display
- Face enrollment and verification using MediaPipe Face Mesh landmarks
- Experimental fingerprint enrollment and verification flow
- Security-settings page for authentication status and biometric data
- Per-user file access through SQLite records and local upload storage

## Technology Stack

- Python and Flask
- SQLite
- Jinja templates
- Bootstrap 5 and Font Awesome
- PyOTP and QRCode
- OpenCV, NumPy, and MediaPipe
- Browser MediaPipe Face Mesh and Camera Utils

## Project Structure

```text
vairam/
├── app.py                    # Flask application and routes
├── face_recognition_system.py
├── fix_database.py           # Database initializer
├── req.txt                   # Python dependencies
├── cloud_storage.db          # Local SQLite database
├── face_data.json            # Face landmark templates
├── face_data/                # Face preview images
├── uploads/                  # User-uploaded files
├── fingerprint_data/         # Reserved fingerprint directory
├── templates/                # Jinja HTML templates
└── virua/                    # Existing local virtual environment
```

## Requirements

- Python 3 with `pip`
- A camera and browser camera permission for face enrollment
- A TOTP-compatible authenticator app
- Internet access for the CDN-hosted frontend and browser MediaPipe assets
- Write access to the project directory for SQLite and uploaded files

Use a Python version supported by the MediaPipe package installed for your platform.

## Installation

Run all commands from the repository root.

### 1. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Or on macOS/Linux:

```bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r req.txt
python -m pip install mediapipe
```

`mediapipe` is required by `face_recognition_system.py` but is not currently listed in `req.txt`.

### 3. Initialize the database

```bash
python fix_database.py
```

This creates `cloud_storage.db`, creates the `users` and `files` tables, and inserts a sample `testuser` record.

> **Warning:** `fix_database.py` deletes the existing `cloud_storage.db` before recreating it. Do not run it against a database you need to keep.

### 4. Start the application

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

## Basic Usage

1. Register an account.
2. Log in with the new account.
3. Optionally enable TOTP from Security Settings.
4. Upload an allowed file from the dashboard.
5. Download or delete previously uploaded files.

Uploads are limited to 16 MiB and these extensions:

```text
txt, pdf, png, jpg, jpeg, gif, doc, docx, mp4, mp3, zip
```

## Known Limitations

- The Flask development server runs with debug mode enabled on `0.0.0.0`.
- The Flask secret key is currently hard-coded in `app.py`.
- Uploaded files and biometric data are not encrypted at rest.
- The fingerprint flow is a browser-side simulation, not WebAuthn or scanner integration.
- Face and fingerprint verification currently require an existing server session and do not complete a logged-out login flow by themselves.
- Face matching is based on landmark distances and does not include liveness or anti-spoofing checks.
- There is no database migration system, CSRF protection, rate limiting, password reset, or email verification.
- The UI uses external CDN assets, so some features require an internet connection.

## Security Before Deployment

Do not expose this prototype to the public Internet without addressing these items:

- Load a private Flask secret key from an environment variable.
- Disable Flask debug mode.
- Run behind a production WSGI server and reverse proxy.
- Add HTTPS, secure session-cookie settings, CSRF protection, and rate limiting.
- Encrypt sensitive files and biometric data at rest.
- Replace the biometric demonstrations with a reviewed authentication design.
- Review every route and permission boundary.

Never publish the populated `cloud_storage.db`, `face_data.json`, `face_data/`, or `uploads/` directories. They may contain credentials, TOTP secrets, biometric templates, face images, or private files. Also exclude virtual environments and generated Python caches from version control.

## License

No license has been added yet. Add a `LICENSE` file before distributing or publishing the project.
