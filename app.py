import os
import sqlite3
import uuid
import base64
from io import BytesIO
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pyotp
import qrcode
from face_recognition_system import face_system

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'mp4', 'mp3', 'zip'}

# Create directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('face_data', exist_ok=True)

def get_db():
    conn = sqlite3.connect('cloud_storage.db')
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def twofa_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('twofa_verified') != True:
            flash('Please verify 2FA first', 'error')
            return redirect(url_for('verify_2fa'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        if not username or not password or not email:
            flash('All fields are required', 'error')
            return redirect(url_for('register'))

        with get_db() as conn:
            # Check if user exists
            user = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?',
                              (username, email)).fetchone()
            if user:
                flash('Username or email already exists', 'error')
                return redirect(url_for('register'))

            # Create new user
            hashed_password = generate_password_hash(password)
            conn.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)',
                        (username, hashed_password, email))
            conn.commit()

            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        with get_db() as conn:
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']

                # Check if twofa is enabled (handle None)
                twofa_enabled = user['twofa_enabled'] if user['twofa_enabled'] is not None else 0

                if twofa_enabled:
                    session['twofa_verified'] = False
                    return redirect(url_for('verify_2fa'))
                else:
                    session['twofa_verified'] = True
                    return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'error')

    return render_template('login.html')

@app.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with get_db() as conn:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

        if not user:
            flash('User not found', 'error')
            return redirect(url_for('login'))

        if request.method == 'POST':
            if user['twofa_secret']:
                totp = pyotp.TOTP(user['twofa_secret'])
                if totp.verify(request.form['otp']):
                    session['twofa_verified'] = True
                    return redirect(url_for('dashboard'))
                else:
                    flash('Invalid 2FA code', 'error')
            else:
                flash('2FA not set up', 'error')

        return render_template('verify_2fa.html')

@app.route('/setup-2fa', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    with get_db() as conn:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

        if not user:
            flash('User not found', 'error')
            return redirect(url_for('login'))

        if request.method == 'POST':
            if user['twofa_secret']:
                totp = pyotp.TOTP(user['twofa_secret'])
                if totp.verify(request.form['otp']):
                    conn.execute('UPDATE users SET twofa_enabled = 1 WHERE id = ?', (session['user_id'],))
                    conn.commit()
                    flash('2FA enabled successfully!', 'success')
                    return redirect(url_for('security_settings'))
                else:
                    flash('Invalid verification code', 'error')
            else:
                flash('2FA secret not found', 'error')

        # Generate secret if not exists
        if not user['twofa_secret']:
            secret = pyotp.random_base32()
            conn.execute('UPDATE users SET twofa_secret = ? WHERE id = ?', (secret, session['user_id']))
            conn.commit()
            user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()

        totp = pyotp.TOTP(user['twofa_secret'])
        provisioning_uri = totp.provisioning_uri(user['username'], issuer_name="SecureCloud")

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_base64 = base64.b64encode(img_bytes.getvalue()).decode()

        return render_template('setup_2fa.html', qr_code=img_base64, secret=user['twofa_secret'])

# Add these routes or update existing ones in app.py

@app.route('/setup-face', methods=['GET', 'POST'])
@login_required
def setup_face():
    if request.method == 'POST':
        if 'face_image' not in request.files:
            flash('No image uploaded', 'error')
            return redirect(url_for('setup_face'))

        file = request.files['face_image']
        if file.filename == '':
            flash('No image selected', 'error')
            return redirect(url_for('setup_face'))

        # Enroll face with MediaPipe
        result = face_system.enroll_face(str(session['user_id']), image_data=file.read())

        if result['success']:
            with get_db() as conn:
                conn.execute('UPDATE users SET face_enrolled = 1 WHERE id = ?', (session['user_id'],))
                conn.commit()

            flash(f'{result["message"]} Total templates: {result.get("num_templates", 1)}', 'success')
            return redirect(url_for('security_settings'))
        else:
            flash(result['message'], 'error')

    return render_template('setup_face.html')

@app.route('/verify-face-multi', methods=['POST'])
def verify_face_multi():
    """Alternative endpoint that returns more detailed face verification info"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'verified': False, 'message': 'Not logged in'})

    if 'face_image' not in request.files:
        return jsonify({'success': False, 'verified': False, 'message': 'No image provided'})

    file = request.files['face_image']
    if file.filename == '':
        return jsonify({'success': False, 'verified': False, 'message': 'No image selected'})

    # Verify face with MediaPipe
    result = face_system.verify_face(str(session['user_id']), image_data=file.read(), threshold=0.65)

    return jsonify({
        'success': result['success'],
        'verified': result.get('verified', False),
        'confidence': result.get('confidence', 0),
        'message': result.get('message', ''),
        'all_scores': result.get('all_scores', []),
        'num_templates': result.get('num_templates', 0)
    })
@app.route('/verify-face', methods=['POST'])
def verify_face():
    if 'user_id' not in session:
        return jsonify({'success': False, 'verified': False, 'message': 'Not logged in'})

    if 'face_image' not in request.files:
        return jsonify({'success': False, 'verified': False, 'message': 'No image provided'})

    file = request.files['face_image']
    if file.filename == '':
        return jsonify({'success': False, 'verified': False, 'message': 'No image selected'})

    # Verify face with MediaPipe
    result = face_system.verify_face(str(session['user_id']), image_data=file.read(), threshold=0.65)

    return jsonify({
        'success': result['success'],
        'verified': result.get('verified', False),
        'confidence': result.get('confidence', 0),
        'message': result.get('message', ''),
        'all_scores': result.get('all_scores', [])
    })

@app.route('/setup-fingerprint', methods=['GET', 'POST'])
@login_required
def setup_fingerprint():
    if request.method == 'POST':
        fingerprint_data = request.form.get('fingerprint_data')
        if fingerprint_data:
            with get_db() as conn:
                conn.execute('UPDATE users SET fingerprint_data = ? WHERE id = ?',
                           (fingerprint_data, session['user_id']))
                conn.commit()
            flash('Fingerprint setup successful!', 'success')
            return redirect(url_for('security_settings'))
        else:
            flash('No fingerprint data received', 'error')

    return render_template('setup_fingerprint.html')

@app.route('/verify-fingerprint', methods=['POST'])
def verify_fingerprint():
    if 'user_id' not in session:
        return jsonify({'success': False})

    fingerprint_data = request.json.get('fingerprint_data')

    with get_db() as conn:
        user = conn.execute('SELECT fingerprint_data FROM users WHERE id = ?',
                          (session['user_id'],)).fetchone()

        if user and user['fingerprint_data'] and user['fingerprint_data'] == fingerprint_data:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False})

@app.route('/dashboard')
@login_required
@twofa_required
def dashboard():
    with get_db() as conn:
        files = conn.execute('SELECT * FROM files WHERE user_id = ? ORDER BY uploaded_at DESC',
                           (session['user_id'],)).fetchall()
        total_size = conn.execute('SELECT SUM(file_size) as total FROM files WHERE user_id = ?',
                                (session['user_id'],)).fetchone()['total'] or 0

    return render_template('dashboard.html',
                         files=files,
                         total_usage=total_size,
                         username=session['username'])



@app.route('/check-face-enrolled', methods=['GET'])
def check_face_enrolled():
    username = request.args.get('username')
    if not username:
        return jsonify({'enrolled': False})

    with get_db() as conn:
        user = conn.execute('SELECT face_enrolled FROM users WHERE username = ?', (username,)).fetchone()

    if user and user['face_enrolled']:
        return jsonify({'enrolled': True})
    return jsonify({'enrolled': False})



@app.route('/upload', methods=['POST'])
@login_required
@twofa_required
def upload_file():
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('dashboard'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('dashboard'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        file.save(file_path)
        file_size = os.path.getsize(file_path)

        with get_db() as conn:
            conn.execute('''INSERT INTO files (user_id, filename, original_filename, file_path, file_size, file_type)
                          VALUES (?, ?, ?, ?, ?, ?)''',
                        (session['user_id'], unique_filename, filename, file_path,
                         file_size, filename.rsplit('.', 1)[1].lower()))
            conn.commit()

        flash('File uploaded successfully!', 'success')
    else:
        flash('File type not allowed', 'error')

    return redirect(url_for('dashboard'))

@app.route('/download/<int:file_id>')
@login_required
@twofa_required
def download_file(file_id):
    with get_db() as conn:
        file = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?',
                          (file_id, session['user_id'])).fetchone()

        if file:
            return send_from_directory(app.config['UPLOAD_FOLDER'],
                                     file['filename'],
                                     as_attachment=True,
                                     download_name=file['original_filename'])
        else:
            flash('File not found', 'error')
            return redirect(url_for('dashboard'))

@app.route('/delete/<int:file_id>', methods=['POST'])
@login_required
@twofa_required
def delete_file(file_id):
    with get_db() as conn:
        file = conn.execute('SELECT * FROM files WHERE id = ? AND user_id = ?',
                          (file_id, session['user_id'])).fetchone()

        if file:
            try:
                os.remove(file['file_path'])
            except:
                pass

            conn.execute('DELETE FROM files WHERE id = ?', (file_id,))
            conn.commit()
            flash('File deleted successfully', 'success')
        else:
            flash('File not found', 'error')

    return redirect(url_for('dashboard'))

@app.route('/security-settings')
@login_required
def security_settings():
    with get_db() as conn:
        user = conn.execute('SELECT twofa_enabled, face_enrolled, fingerprint_data FROM users WHERE id = ?',
                          (session['user_id'],)).fetchone()

        # Handle case where user might not have these columns
        if user is None:
            flash('User data not found', 'error')
            return redirect(url_for('dashboard'))

        # Safely get values with defaults
        twofa_enabled = user['twofa_enabled'] if user['twofa_enabled'] is not None else 0
        face_enabled = user['face_enrolled'] if user['face_enrolled'] is not None else 0
        fingerprint_enabled = user['fingerprint_data'] is not None and user['fingerprint_data'] != ''

    # Get face info with error handling
    try:
        face_info = face_system.get_face_info(str(session['user_id']))
        face_templates = face_info.get('templates', 0) if face_info.get('success', False) else 0
        face_landmarks = face_info.get('landmarks_per_template', [0])[0] if face_info.get('templates', 0) > 0 else 0
    except Exception as e:
        print(f"Error getting face info: {e}")
        face_templates = 0
        face_landmarks = 0

    # Get face preview with error handling
    try:
        face_preview = face_system.get_face_preview(str(session['user_id']))
    except Exception as e:
        print(f"Error getting face preview: {e}")
        face_preview = None

    return render_template('security_settings.html',
                         twofa_enabled=twofa_enabled,
                         face_enabled=face_enabled,
                         face_templates=face_templates,
                         face_landmarks=face_landmarks,
                         face_preview=face_preview,
                         fingerprint_enabled=fingerprint_enabled)

@app.route('/delete-face-data', methods=['POST'])
@login_required
def delete_face_data():
    result = face_system.delete_face_data(str(session['user_id']))

    if result['success']:
        with get_db() as conn:
            conn.execute('UPDATE users SET face_enrolled = 0 WHERE id = ?', (session['user_id'],))
            conn.commit()
        flash('Face data deleted successfully', 'success')
    else:
        flash(result['message'], 'error')

    return redirect(url_for('security_settings'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Initialize database
    print("\n" + "="*50)
    print("🚀 SecureCloud Server Starting...")
    print("📍 Visit: http://localhost:5000")
    print("🔒 Face Recognition with MediaPipe (468 landmarks)")
    print("="*50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
