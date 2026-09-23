import io
import os
import sqlite3
from datetime import timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, g, make_response, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'careerhub-secret-key')
app.config['DATABASE'] = os.environ.get('DATABASE', os.path.join(os.path.dirname(__file__), 'careerhub.db'))
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
# ============================================================
# INTENTIONAL LAB VULNERABILITY
# Vulnerability: Security Misconfiguration
# Location: Flask response headers
# Purpose: Leave optional browser security headers absent for local observation while keeping
# production-style debug and network-boundary settings safe.
# Secure remediation: Set X-Content-Type-Options, Content-Security-Policy, Referrer-Policy,
# Permissions-Policy, and (only over HTTPS) Strict-Transport-Security.
# ============================================================
app.config['DEBUG'] = False
app.config['PROPAGATE_EXCEPTIONS'] = False
# Secure example (only after HTTPS is enabled):
# response.headers.update({'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': "default-src 'self'",
#                          'Referrer-Policy': 'strict-origin-when-cross-origin', 'Permissions-Policy': 'geolocation=()',
#                          'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'})

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
login_attempts = {}


def connect_db():
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    return db


def get_db():
    if 'db' not in g:
        g.db = connect_db()
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


@app.errorhandler(403)
def forbidden(error):
    return render_template('error_403.html'), 403


@app.errorhandler(404)
def not_found(error):
    return render_template('error_404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('error_500.html'), 500


def init_db():
    db = connect_db()
    db.execute('PRAGMA foreign_keys = ON')
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'candidate',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            salary TEXT NOT NULL,
            description TEXT NOT NULL,
            requirements TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            phone TEXT,
            skills TEXT,
            bio TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            resume TEXT,
            cover_message TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    db.commit()
    seed_data(db)
    db.close()


def seed_data(db):
    # Demo credentials are intentionally NOT stored in source control.
    # Set these environment variables locally before running the lab.
    sample_users = [
        ('Admin', os.environ.get('CAREERHUB_ADMIN_EMAIL', 'admin@careerhub.local'),
         os.environ.get('CAREERHUB_ADMIN_PASSWORD'), 'admin'),
        ('Alice Johnson', os.environ.get('CAREERHUB_ALICE_EMAIL', 'alice@careerhub.local'),
         os.environ.get('CAREERHUB_ALICE_PASSWORD'), 'candidate'),
        ('Bob Williams', os.environ.get('CAREERHUB_BOB_EMAIL', 'bob@careerhub.local'),
         os.environ.get('CAREERHUB_BOB_PASSWORD'), 'candidate'),
    ]

    # Only seed accounts when passwords are explicitly supplied locally.
    sample_users = [user for user in sample_users if user[2]]

    for name, email, password, role in sample_users:
        existing = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing is None:
            db.execute(
                'INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)',
                (name, email, generate_password_hash(password), role),
            )

    jobs = [
        ('Python Developer', 'TechNova', 'Remote', '$95,000', 'Build modern Python services for internal products.', 'Python, Flask, PostgreSQL'),
        ('Frontend Developer', 'PixelCraft', 'New York', '$85,000', 'Create polished and responsive interfaces for customers.', 'HTML, CSS, JavaScript'),
        ('Backend Developer', 'CloudBridge', 'Austin', '$100,000', 'Maintain scalable APIs and backend infrastructure.', 'Python, REST APIs, SQL'),
        ('Software Engineer', 'BrightPath', 'Chicago', '$110,000', 'Collaborate on product features and deployment pipelines.', 'Python, Testing, CI/CD'),
        ('Data Analyst', 'InsightLab', 'Remote', '$90,000', 'Turn business data into actionable insights.', 'SQL, Excel, Reporting'),
        ('QA Engineer', 'QualityWorks', 'Denver', '$80,000', 'Ensure product quality through test automation and manual validation.', 'Testing, Selenium, QA'),
        ('Full Stack Developer', 'OpenGrid', 'Seattle', '$105,000', 'Own full product workflows from UI to services.', 'Flask, JavaScript, SQLite'),
        ('Cybersecurity Analyst', 'SecureNet', 'Boston', '$115,000', 'Monitor systems and support security improvements.', 'Security, SIEM, Threat Analysis'),
    ]

    for title, company, location, salary, description, requirements in jobs:
        existing = db.execute('SELECT id FROM jobs WHERE title = ? AND company = ?', (title, company)).fetchone()
        if existing is None:
            db.execute(
                'INSERT INTO jobs (title, company, location, salary, description, requirements) VALUES (?, ?, ?, ?, ?, ?)',
                (title, company, location, salary, description, requirements),
            )

    db.commit()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_user():
    user = None
    if session.get('user_id'):
        user = get_db().execute('SELECT id, name, email, role FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    return {'current_user': user}


@app.route('/')
def index():
    jobs = get_db().execute('SELECT * FROM jobs ORDER BY created_at DESC LIMIT 6').fetchall()
    return render_template('index.html', jobs=jobs)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not name or not email or not password or not confirm_password:
            flash('Please complete all fields.', 'danger')
            return render_template('register.html')

        if '@' not in email or '.' not in email:
            flash('Please provide a valid email address.', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')

        existing_user = get_db().execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing_user:
            flash('An account with that email already exists.', 'danger')
            return render_template('register.html')

        get_db().execute(
            'INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)',
            (name, email, generate_password_hash(password), 'candidate'),
        )
        get_db().commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        # ============================================================
        # INTENTIONAL LAB VULNERABILITY
        # Vulnerability: Missing Account Lockout
        # Location: /login
        # Purpose: Demonstrate that repeated failed logins are not throttled or locked out.
        # Secure remediation: Track failed attempts and temporarily lock the account after repeated failures.
        # ============================================================
        # The counter is deliberately informational only: no lockout, delay, or rate limit is enforced.
        login_attempts[email] = login_attempts.get(email, 0) + 1
        # Secure example (keep server-side, with generic client errors):
        # if failed_attempts_for(email) >= 5: temporarily_lock_account(email)

        # ============================================================
        # INTENTIONAL LAB VULNERABILITY
        # Vulnerability: Insufficient Session Expiration
        # Location: /login
        # Purpose: Make the user session persistent for a long period after login.
        # Secure remediation: Use short-lived, non-permanent sessions and expire them on logout or inactivity.
        # ============================================================
        session.permanent = True
        # Secure example: session.permanent = False; rotate the session identifier after authentication.

        user = get_db().execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if user and check_password_hash(user['password'], password):
            login_attempts.pop(email, None)
            session.clear()
            session['user_id'] = user['id']
            session['role'] = user['role']
            # No session-id rotation is performed after authentication in this intentional lab weakness.
            flash(f"Welcome back, {user['name']}!", 'success')
            if user['role'] == 'admin':
                return redirect(url_for('admin'))
            return redirect(url_for('dashboard'))

        flash('Invalid email or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    # ============================================================
    # INTENTIONAL LAB VULNERABILITY
    # Vulnerability: Insufficient Session Expiration
    # Location: /logout and authenticated pages
    # Purpose: The long-lived, permanent session is not invalidated at logout; its user_id remains usable.
    # Secure remediation: Clear and invalidate the server-side session on logout, rotate session IDs on login,
    # and enforce short absolute and inactivity expirations on every authenticated request.
    # ============================================================
    # Secure example: session.clear(); revoke_server_side_session(session_id)
    # Keep the intentional long-lived session behavior, but mark the navigation as logged out.
    session['logged_out'] = True
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    user = get_db().execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    profile = get_db().execute('SELECT * FROM profiles WHERE user_id = ?', (user['id'],)).fetchone()
    applications = get_db().execute(
        'SELECT a.*, j.title FROM applications a JOIN jobs j ON j.id = a.job_id WHERE a.user_id = ? ORDER BY a.created_at DESC LIMIT 5',
        (user['id'],),
    ).fetchall()

    counts = {
        'total': get_db().execute('SELECT COUNT(*) AS count FROM applications WHERE user_id = ?', (user['id'],)).fetchone()['count'],
        'pending': get_db().execute('SELECT COUNT(*) AS count FROM applications WHERE user_id = ? AND status = ?', (user['id'], 'pending')).fetchone()['count'],
        'shortlisted': get_db().execute('SELECT COUNT(*) AS count FROM applications WHERE user_id = ? AND status = ?', (user['id'], 'shortlisted')).fetchone()['count'],
        'interviews': get_db().execute('SELECT COUNT(*) AS count FROM applications WHERE user_id = ? AND status = ?', (user['id'], 'interview')).fetchone()['count'],
    }

    # ============================================================
    # INTENTIONAL LAB VULNERABILITY
    # Vulnerability: Missing / Improper Cache-Control Header
    # Location: /dashboard
    # Purpose: Allow sensitive dashboard content to be cached in shared or browser caches.
    # Secure remediation: Set Cache-Control: no-store for auth-only pages.
    # ============================================================
    response = make_response(render_template('dashboard.html', user=user, profile=profile, applications=applications, counts=counts))
    response.headers['Cache-Control'] = 'public, max-age=300'
    # Secure example: response.headers.update({'Cache-Control': 'no-store, no-cache, must-revalidate, private', 'Pragma': 'no-cache'})
    return response


@app.route('/jobs')
def jobs():
    query = request.args.get('search', request.args.get('q', '')).strip()
    if query:
        # ============================================================
        # INTENTIONAL LAB VULNERABILITY
        # Vulnerability: SQL Injection
        # Location: /jobs?search=
        # Purpose: Demonstrate unsafe SQL construction from the search term.
        # Secure remediation: Use parameterized SQLite placeholders instead of string interpolation.
        # ============================================================
        raw_sql = f"SELECT * FROM jobs WHERE title LIKE '%{query}%' OR company LIKE '%{query}%' OR location LIKE '%{query}%' OR description LIKE '%{query}%' OR requirements LIKE '%{query}%' ORDER BY created_at DESC"
        jobs = get_db().execute(raw_sql).fetchall()
        # Secure example:
        # jobs = get_db().execute('SELECT * FROM jobs WHERE title LIKE ? OR company LIKE ? OR location LIKE ? OR description LIKE ? OR requirements LIKE ? ORDER BY created_at DESC', tuple(f'%{query}%' for _ in range(5))).fetchall()
    else:
        jobs = get_db().execute('SELECT * FROM jobs ORDER BY created_at DESC').fetchall()
    return render_template('jobs.html', jobs=jobs, query=query)


@app.route('/job/<int:job_id>')
def job_details(job_id):
    job = get_db().execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    return render_template('job_details.html', job=job)


@app.route('/apply/<int:job_id>', methods=['GET', 'POST'])
@login_required
def apply(job_id):
    job = get_db().execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    if request.method == 'POST':
        resume_file = request.files.get('resume')
        resume_name = None
        if resume_file and resume_file.filename:
            filename = secure_filename(resume_file.filename)
            resume_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            resume_file.save(resume_path)
            resume_name = filename

        cover_message = request.form.get('cover_message', '').strip()
        get_db().execute(
            'INSERT INTO applications (user_id, job_id, resume, cover_message, status) VALUES (?, ?, ?, ?, ?)',
            (session['user_id'], job_id, resume_name, cover_message, 'pending'),
        )
        get_db().commit()
        flash('Application submitted successfully.', 'success')
        return redirect(url_for('applications'))

    return render_template('apply.html', job=job)


@app.route('/applications')
@login_required
def applications():
    user = get_db().execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    if user['role'] == 'admin':
        applications = get_db().execute(
            'SELECT a.*, j.title, u.name FROM applications a JOIN jobs j ON j.id = a.job_id JOIN users u ON u.id = a.user_id ORDER BY a.created_at DESC'
        ).fetchall()
    else:
        applications = get_db().execute(
            'SELECT a.*, j.title FROM applications a JOIN jobs j ON j.id = a.job_id WHERE a.user_id = ? ORDER BY a.created_at DESC',
            (user['id'],),
        ).fetchall()
    # ============================================================
    # INTENTIONAL LAB VULNERABILITY
    # Vulnerability: Missing / Improper Cache-Control Header
    # Location: /applications
    # Purpose: Leave authenticated, user-specific application data without cache protections.
    # Secure remediation: Set Cache-Control: no-store, no-cache, must-revalidate, private and Pragma: no-cache.
    # ============================================================
    response = make_response(render_template('applications.html', applications=applications, is_admin=(user['role'] == 'admin')))
    response.headers['Cache-Control'] = 'private, max-age=120'
    # Secure example: response.headers.update({'Cache-Control': 'no-store, no-cache, must-revalidate, private', 'Pragma': 'no-cache'})
    return response


@app.route('/application/<int:application_id>', methods=['GET', 'POST'])
@login_required
def application_details(application_id):
    # ============================================================
    # INTENTIONAL LAB VULNERABILITY
    # Vulnerability: IDOR / BOLA
    # Location: /application/<id>
    # Purpose: Allow any authenticated user to view another user's application by changing the ID.
    # Secure remediation: Enforce ownership or admin authorization before loading the application record.
    # ============================================================
    application = get_db().execute(
        'SELECT a.*, j.title, u.name FROM applications a JOIN jobs j ON j.id = a.job_id JOIN users u ON u.id = a.user_id WHERE a.id = ?',
        (application_id,),
    ).fetchone()
    # Secure example:
    # if application and application['user_id'] != session['user_id'] and session.get('role') != 'admin': abort(403)
    # Equivalent ownership check: application.user_id == current_user.id
    if not application:
        flash('Application not found.', 'danger')
        return redirect(url_for('applications'))

    if request.method == 'POST' and session.get('role') == 'admin':
        new_status = request.form.get('status', 'pending').strip().lower()
        if new_status not in {'pending', 'shortlisted', 'interview', 'rejected'}:
            new_status = 'pending'
        get_db().execute('UPDATE applications SET status = ? WHERE id = ?', (new_status, application_id))
        get_db().commit()
        flash('Application status updated.', 'success')
        return redirect(url_for('application_details', application_id=application_id))

    return render_template('application_details.html', application=application)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = get_db().execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    profile = get_db().execute('SELECT * FROM profiles WHERE user_id = ?', (user['id'],)).fetchone()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        skills = request.form.get('skills', '').strip()
        bio = request.form.get('professional_summary', '').strip()

        if not name or not email:
            flash('Name and email are required.', 'danger')
            return render_template('profile.html', user=user, profile=profile)

        if email != user['email']:
            existing = get_db().execute('SELECT id FROM users WHERE email = ? AND id != ?', (email, user['id'])).fetchone()
            if existing:
                flash('A user with that email already exists.', 'danger')
                return render_template('profile.html', user=user, profile=profile)

        get_db().execute('UPDATE users SET name = ?, email = ? WHERE id = ?', (name, email, user['id']))
        if profile:
            get_db().execute('UPDATE profiles SET phone = ?, skills = ?, bio = ? WHERE user_id = ?', (phone, skills, bio, user['id']))
        else:
            get_db().execute('INSERT INTO profiles (user_id, phone, skills, bio) VALUES (?, ?, ?, ?)', (user['id'], phone, skills, bio))
        get_db().commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('profile'))

    # ============================================================
    # INTENTIONAL LAB VULNERABILITY
    # Vulnerability: Missing / Improper Cache-Control Header
    # Location: /profile
    # Purpose: Allow a browser to retain user-specific profile content after use.
    # Secure remediation: Set Cache-Control: no-store, no-cache, must-revalidate, private and Pragma: no-cache.
    # ============================================================
    response = make_response(render_template('profile.html', user=user, profile=profile))
    response.headers['Cache-Control'] = 'private, max-age=120'
    # Secure example: response.headers.update({'Cache-Control': 'no-store, no-cache, must-revalidate, private', 'Pragma': 'no-cache'})
    return response


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        upload_file = request.files.get('file')
        if upload_file and upload_file.filename:
            # ============================================================
            # INTENTIONAL LAB VULNERABILITY
            # Vulnerability: Unrestricted File Upload
            # Location: /upload
            # Purpose: Allow uploaded files to be stored without extension or content validation.
            # Secure remediation: Validate file type, size, and content before storing uploads.
            # ============================================================
            filename = secure_filename(upload_file.filename)
            upload_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # Secure example: validate an extension allowlist, inspect content, cap file size, use a random
            # filename, and store outside the executable/static web root with non-executable permissions.
            flash('File uploaded successfully.', 'success')
        else:
            flash('Please choose a file to upload.', 'danger')
    return render_template('upload.html')


@app.route('/download')
@login_required
def download_file():
    # ============================================================
    # INTENTIONAL LAB VULNERABILITY
    # Vulnerability: Path Traversal
    # Location: /download?file=
    # Purpose: Improperly trust the supplied relative path. The handler refuses paths outside this project,
    # limiting the lab to harmless CareerHub files.
    # Secure remediation: Use pathlib canonical paths, an allowed directory check, and a filename allowlist.
    # ============================================================
    requested_file = request.args.get('file', '')
    project_root = Path(app.root_path).resolve()
    file_path = (Path(app.config['UPLOAD_FOLDER']) / requested_file).resolve()
    # The missing upload-directory validation is intentional. This boundary keeps all lab reads inside CareerHub.
    if project_root not in file_path.parents and file_path != project_root:
        flash('Only CareerHub project files are available in this local lab.', 'danger')
        return redirect(url_for('upload'))
    # Secure example:
    # upload_dir = Path(app.config['UPLOAD_FOLDER']).resolve()
    # if Path(requested_file).name != requested_file or upload_dir not in file_path.parents: abort(400)
    if not file_path.is_file():
        flash('File not found.', 'danger')
        return redirect(url_for('upload'))
    return send_file(str(file_path), as_attachment=True)


@app.route('/debug')
@login_required
def debug_info():
    # ============================================================
    # INTENTIONAL LAB VULNERABILITY
    # Vulnerability: Information Disclosure
    # Location: /debug
    # Purpose: Expose controlled implementation details and a local database error to the browser.
    # Secure remediation: Return generic errors, log details server-side, and never send stack traces,
    # database errors, credentials, or paths to a user.
    # ============================================================
    user = get_db().execute('SELECT id, name, email FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    try:
        get_db().execute('SELECT local_lab_missing_column FROM users').fetchone()
    except sqlite3.Error as error:
        return f"User: {user['name']}\nEmail: {user['email']}\nDatabase: {app.config['DATABASE']}\nDatabase error: {error}", 500
    # Secure example: current_app.logger.exception('debug endpoint failure'); return 'An unexpected error occurred.', 500


@app.route('/admin')
@login_required
def admin():
    user = get_db().execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    # ============================================================
    # Secure example: if not user or user['role'] != 'admin': abort(403)
    # INTENTIONAL LAB VULNERABILITY
    # Vulnerability: Broken Access Control
    # Location: /admin
    # Purpose: Allow any authenticated user to view admin data.
    # Secure remediation: Enforce role-based access and redirect non-admin users away from admin routes.
    # ============================================================
    users = get_db().execute('SELECT id, name, email, role, created_at FROM users ORDER BY created_at DESC').fetchall()
    jobs = get_db().execute('SELECT * FROM jobs ORDER BY created_at DESC').fetchall()
    applications = get_db().execute(
        'SELECT a.*, j.title, u.name FROM applications a JOIN jobs j ON j.id = a.job_id JOIN users u ON u.id = a.user_id ORDER BY a.created_at DESC'
    ).fetchall()
    stats = {
        'users': get_db().execute('SELECT COUNT(*) AS count FROM users').fetchone()['count'],
        'jobs': get_db().execute('SELECT COUNT(*) AS count FROM jobs').fetchone()['count'],
        'applications': get_db().execute('SELECT COUNT(*) AS count FROM applications').fetchone()['count'],
    }
    return render_template('admin.html', users=users, jobs=jobs, applications=applications, stats=stats)


init_db()


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
