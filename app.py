import json
import os
import logging
import io
import threading
import time
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from github import Github, GithubException
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError
import schedule
import smtplib
from email.mime.text import MIMEText
import requests
from werkzeug.utils import secure_filename
from google.auth import default
from google.auth.exceptions import RefreshError
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from flask_talisman import Talisman
from flask_login import LoginManager, current_user
from flask_login import UserMixin



# Enhanced logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
logger = logging.getLogger(__name__)

from config import Config

app = Flask(__name__, static_url_path='/static')
csp = {
    'default-src': ['\'self\'', 'https://fonts.googleapis.com', 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'],
    'script-src': ['\'self\'', 'https://cdnjs.cloudflare.com', '\'unsafe-inline\''],
    'style-src': ['\'self\'', 'https://fonts.googleapis.com', 'https://cdnjs.cloudflare.com', '\'unsafe-inline\''],
    'font-src': ['\'self\'', 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'],
}

Talisman(app, content_security_policy=csp)

app.config.from_object(Config)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

# Enable CORS
CORS(app)

# Setup caching
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Setup rate limiting
limiter = Limiter(key_func=get_remote_address)
limiter.init_app(app)

# Setup database connection (using SQLAlchemy as an example)
from flask_sqlalchemy import SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///taskwhiz.db'
db = SQLAlchemy(app)

# User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    settings = db.Column(db.JSON)

# Create tables
with app.app_context():
    db.create_all()

SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students',
    'https://www.googleapis.com/auth/classroom.rosters.readonly',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/classroom.coursework.me',
    'https://www.googleapis.com/auth/classroom.student-submissions.students.readonly',
    'https://www.googleapis.com/auth/classroom.profile.emails',
    'https://www.googleapis.com/auth/classroom.profile.photos',
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/classroom.courses'
]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'credentials' not in session:
            return redirect(url_for('authorize'))
        return f(*args, **kwargs)
    return decorated_function

@cache.memoize(timeout=300)
def get_credentials():
    if 'credentials' not in session:
        return None
    credentials = Credentials(**session['credentials'])
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            session['credentials'] = credentials_to_dict(credentials)
        except RefreshError:
            session.clear()
            return None
    return credentials

@app.before_request
def before_request():
    if 'credentials' in session:
        get_credentials()

@app.context_processor
def inject_user():
    if 'credentials' in session:
        credentials = get_credentials()
        if not credentials:
            session.clear()
            return dict()
        try:
            user_info_service = build('oauth2', 'v2', credentials=credentials)
            user_info = user_info_service.userinfo().get().execute()
            return dict(user_info=user_info)
        except Exception as e:
            logger.error(f"Error fetching user info: {str(e)}")
            session.clear()
    return dict()

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    # Return your User object here
    return User.query.get(int(user_id))

@app.route('/check_auth_status')
@cache.cached(timeout=60)
def check_auth_status():
    if 'credentials' in session:
        credentials = get_credentials()
        if credentials:
            return jsonify({'authenticated': True})
    return jsonify({'authenticated': False})

def send_email(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = app.config['EMAIL_ADDRESS']
    msg['To'] = app.config['EMAIL_ADDRESS']

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
            smtp_server.login(app.config['EMAIL_ADDRESS'], app.config['EMAIL_PASSWORD'])
            smtp_server.sendmail(app.config['EMAIL_ADDRESS'], app.config['EMAIL_ADDRESS'], msg.as_string())
        logger.info(f"Email sent: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")

def check_and_submit_assignments():
    with app.app_context():
        credentials = get_credentials()
        if not credentials:
            logger.warning("No valid credentials found")
            return

        classroom_service = build('classroom', 'v1', credentials=credentials)
        drive_service = build('drive', 'v3', credentials=credentials)
        github_client = Github(app.config['GITHUB_TOKEN'])

    try:
        repo = github_client.get_repo(app.config['GITHUB_REPO'])
        courses = classroom_service.courses().list(pageSize=10).execute()

        for course in courses.get('courses', []):
            course_work = classroom_service.courses().courseWork().list(courseId=course['id']).execute()
            for work in course_work.get('courseWork', []):
                due_date = parse_due_date(work.get('dueDate', {}))
                if due_date and (due_date - datetime.now()).days <= 1:
                    try:
                        file_path = f"{work['title']}/submission.txt"
                        file_content = repo.get_contents(file_path).decoded_content
                        submit_assignment(classroom_service, drive_service, course['id'], work['id'], work['title'], file_content)
                        logger.info(f"Automatically submitted assignment: {work['title']}")
                    except GithubException:
                        logger.warning(f"No submission file found for {work['title']}")
    except Exception as e:
        logger.error(f"Error in check_and_submit_assignments: {str(e)}")

def submit_assignment(classroom_service, drive_service, course_id, course_work_id, filename, file_content):
    try:
        student_submissions = classroom_service.courses().courseWork().studentSubmissions().list(
            courseId=course_id,
            courseWorkId=course_work_id,
            userId='me'
        ).execute().get('studentSubmissions', [])
        
        if not student_submissions:
            logger.warning(f"No submissions found for course ID {course_id} and coursework ID {course_work_id}")
            return

        student_submission = student_submissions[0]

        file_metadata = {'name': filename}
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='text/plain', resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        attachment = classroom_service.courses().courseWork().studentSubmissions().modifyAttachments(
            courseId=course_id,
            courseWorkId=course_work_id,
            id=student_submission['id'],
            body={
                'addAttachments': [{
                    'driveFile': {
                        'id': file.get('id')
                    }
                }]                
            }
        ).execute()

        classroom_service.courses().courseWork().studentSubmissions().turnIn(
            courseId=course_id,
            courseWorkId=course_work_id,
            id=student_submission['id']
        ).execute()

        logger.info(f"Successfully submitted assignment: {filename}")
    except HttpError as e:
        error_details = json.loads(e.content.decode('utf-8'))
        logger.error(f"HTTP Error {e.resp.status}: {error_details['error']['message']}")
    except Exception as e:
        logger.error(f"Error submitting assignment: {str(e)}")
        
def parse_due_date(due_date):
    if not due_date:
        return None
    return datetime(year=due_date.get('year', 1), month=due_date.get('month', 1), day=due_date.get('day', 1))

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

scheduler_thread = threading.Thread(target=run_scheduler)
scheduler_thread.daemon = True
scheduler_thread.start()

schedule.every(1).hours.do(check_and_submit_assignments)

def get_google_auth_flow():
    flow = Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True))
    return flow

@app.route('/')
@cache.cached(timeout=300)
def index():
    return render_template('index.html')

@app.route('/check_auth')
@limiter.limit("10/minute")
def check_auth():
    if 'credentials' not in session:
        return jsonify({'status': 'Not authenticated'})
    credentials = Credentials(**session['credentials'])
    if credentials.expired:
        return jsonify({'status': 'Credentials expired'})
    return jsonify({
        'status': 'Authenticated',
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'scopes': credentials.scopes
    })

@app.route('/authorize')
def authorize():
    flow = get_google_auth_flow()
    authorization_url, _ = flow.authorization_url(prompt='consent')
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    flow = get_google_auth_flow()
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session['credentials'] = credentials_to_dict(credentials)
    return redirect(url_for('dashboard'))

def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

@app.route('/dashboard')
@login_required
@cache.cached(timeout=60)
def dashboard():
    if 'credentials' not in session:
        return redirect('authorize')
    
    credentials = Credentials(**session['credentials'])
    classroom_service = build('classroom', 'v1', credentials=credentials)
    
    courses = classroom_service.courses().list(pageSize=10).execute().get('courses', [])
    assignments = []

    for course in courses:
        course_work = classroom_service.courses().courseWork().list(courseId=course['id']).execute().get('courseWork', [])
        
        for work in course_work:
            # Fetch the submission status for this assignment
            submissions = classroom_service.courses().courseWork().studentSubmissions().list(
                courseId=course['id'],
                courseWorkId=work['id'],
                userId='me'
            ).execute().get('studentSubmissions', [])

            submission_status = 'Not submitted'
            if submissions:
                state = submissions[0]['state']
                if state == 'TURNED_IN':
                    submission_status = 'Submitted'
                elif state == 'RETURNED':
                    submission_status = 'Graded'

            due_date = work.get('dueDate')
            if due_date:
                due_date = datetime(year=due_date['year'], month=due_date['month'], day=due_date['day'])
            
            assignment = {
                'id': work['id'],
                'title': work['title'],
                'course': course['name'],
                'due_date': due_date.strftime('%Y-%m-%d') if due_date else 'No due date',
                'status': submission_status,
                'description': work.get('description', 'No description available'),
                'created_date': work['creationTime'],
                'last_modified': work['updateTime']
            }

            # If the assignment is graded, include the grade
            if submission_status == 'Graded' and 'assignedGrade' in submissions[0]:
                assignment['grade'] = submissions[0]['assignedGrade']
                assignment['total_marks'] = work.get('maxPoints', 'N/A')

            assignments.append(assignment)

    total_assignments = len(assignments)
    completed_assignments = sum(1 for a in assignments if a['status'] in ['Submitted', 'Graded'])
    upcoming_deadlines = sum(1 for a in assignments if a['due_date'] != 'No due date' and datetime.strptime(a['due_date'], '%Y-%m-%d') > datetime.now())

    return render_template('dashboard.html', 
                           total_assignments=total_assignments,
                           completed_assignments=completed_assignments,
                           upcoming_deadlines=upcoming_deadlines,
                           assignments=assignments)

@app.route('/error')
def error_page():
    error_message = request.args.get('message', 'An unknown error occurred.')
    logger.error(f"Error page accessed: {error_message}")
    return render_template('error.html', error_message=error_message)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/submit/<assignment_id>', methods=['POST'])
@login_required
@limiter.limit("5/minute")
def submit_assignment_manually(assignment_id):
    logger.info(f"Attempting to submit assignment {assignment_id}")
    credentials = get_credentials()

    classroom_service = build('classroom', 'v1', credentials=credentials)
    drive_service = build('drive', 'v3', credentials=credentials)

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'})
    
    try:
        file_content = file.read()
        course_id = None
        course_work_id = None
        
        courses = classroom_service.courses().list(pageSize=10).execute()
        for course in courses.get('courses', []):
            course_work = classroom_service.courses().courseWork().list(courseId=course['id']).execute()
            for work in course_work.get('courseWork', []):
                if work['id'] == assignment_id:
                    course_id = course['id']
                    course_work_id = work['id']
                    break
            if course_id:
                break
        
        if not course_id or not course_work_id:
            return jsonify({'success': False, 'message': 'Assignment not found'})
        
        student_submissions = classroom_service.courses().courseWork().studentSubmissions().list(
            courseId=course_id,
            courseWorkId=course_work_id,
            userId='me'
        ).execute().get('studentSubmissions', [])
        
        if not student_submissions:
            return jsonify({'success': False, 'message': 'No submission found for this assignment'})

        student_submission = student_submissions[0]

        file_metadata = {'name': secure_filename(file.filename)}
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='text/plain', resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        attachment = classroom_service.courses().courseWork().studentSubmissions().modifyAttachments(
            courseId=course_id,
            courseWorkId=course_work_id,
            id=student_submission['id'],
            body={
                'addAttachments': [{
                    'driveFile': {
                        'id': file.get('id')
                    }
                }]
            }
        ).execute()

        classroom_service.courses().courseWork().studentSubmissions().turnIn(
            courseId=course_id,
            courseWorkId=course_work_id,
            id=student_submission['id']
        ).execute()

        logger.info(f"Assignment {assignment_id} submitted successfully")
        return jsonify({'success': True, 'message': 'Assignment submitted successfully'})
    except HttpError as e:
        error_details = json.loads(e.content.decode('utf-8'))
        error_message = error_details.get('error', {}).get('message', 'Unknown error occurred')
        logger.error(f"HTTP Error {e.resp.status}: {error_message}")
        return jsonify({'success': False, 'message': f"Error submitting assignment: {error_message}"})
    except Exception as e:
        logger.error(f"Unexpected error submitting assignment {assignment_id}: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Unexpected error submitting assignment: {str(e)}'})

@app.route('/revoke')
@login_required
def revoke():
    credentials = Credentials(**session['credentials'])
    revoke = requests.post('https://oauth2.googleapis.com/revoke',
        params={'token': credentials.token},
        headers = {'content-type': 'application/x-www-form-urlencoded'})
    status_code = getattr(revoke, 'status_code')
    if status_code == 200:
        return redirect(url_for('authorize'))
    return redirect(url_for('index'))

@app.route('/assignments')
@login_required
@cache.cached(timeout=300)
def assignments():
    credentials = get_credentials()
    classroom_service = build('classroom', 'v1', credentials=credentials)
    
    try:
        courses = classroom_service.courses().list(pageSize=10).execute()
        all_assignments = []

        for course in courses.get('courses', []):
            course_work = classroom_service.courses().courseWork().list(courseId=course['id']).execute()
            for work in course_work.get('courseWork', []):
                due_date = parse_due_date(work.get('dueDate', {}))
                assignment = {
                    'id': work['id'],
                    'title': work['title'],
                    'course': course['name'],
                    'due_date': due_date.strftime('%Y-%m-%d') if due_date else 'No due date',
                    'description': work.get('description', 'No description available')
                }
                all_assignments.append(assignment)
        
        return render_template('assignments.html', assignments=all_assignments)
    except Exception as e:
        logger.error(f"Error fetching assignments: {str(e)}")
        flash("Failed to load assignments. Please try again later.", "error")
        return redirect(url_for('dashboard'))

@app.route('/courses')
@login_required
@cache.cached(timeout=300)
def courses():
    credentials = get_credentials()
    
    try:
        classroom_service = build('classroom', 'v1', credentials=credentials)
        courses = classroom_service.courses().list(pageSize=10).execute()
        return render_template('courses.html', courses=courses.get('courses', []))
    except Exception as e:
        logger.error(f"Error fetching courses: {str(e)}")
        flash("Failed to load courses. Please try again later.", "error")
        return redirect(url_for('dashboard'))

@app.route('/profile')
@login_required
@cache.cached(timeout=300)
def profile():
    credentials = get_credentials()
    
    try:
        user_info_service = build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()
        return render_template('profile.html', user_info=user_info)
    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}")
        return redirect(url_for('error_page', message="Failed to load user profile"))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    credentials = get_credentials()
    user_info_service = build('oauth2', 'v2', credentials=credentials)
    user_info = user_info_service.userinfo().get().execute()

    if request.method == 'POST':
        email_notifications = 'email_notifications' in request.form
        github_token = request.form.get('github_token')
        custom_setting = request.form.get('custom_setting')

        user = User.query.filter_by(email=user_info['email']).first()
        if not user:
            user = User(email=user_info['email'])
            db.session.add(user)

        user.settings = {
            'email_notifications': email_notifications,
            'github_token': github_token,
            'custom_setting': custom_setting
        }
        db.session.commit()

        app.config['EMAIL_NOTIFICATIONS'] = email_notifications
        app.config['GITHUB_TOKEN'] = github_token

        flash('Settings updated successfully', 'success')
        return redirect(url_for('settings'))

    user = User.query.filter_by(email=user_info['email']).first()
    user_settings = user.settings if user else {}

    return render_template('settings.html', user_settings=user_settings, user_info=user_info)

@app.route('/update_settings', methods=['POST'])
@login_required
@limiter.limit("5/minute")
def update_settings():
    credentials = get_credentials()
    user_info_service = build('oauth2', 'v2', credentials=credentials)
    user_info = user_info_service.userinfo().get().execute()

    email_notifications = 'email_notifications' in request.form
    github_token = request.form.get('github_token')
    custom_setting = request.form.get('custom_setting')

    user = User.query.filter_by(email=user_info['email']).first()
    if not user:
        user = User(email=user_info['email'])
        db.session.add(user)

    user.settings = {
        'email_notifications': email_notifications,
        'github_token': github_token,
        'custom_setting': custom_setting
    }
    db.session.commit()

    app.config['EMAIL_NOTIFICATIONS'] = email_notifications
    app.config['GITHUB_TOKEN'] = github_token

    flash('Settings updated successfully', 'success')
    return redirect(url_for('settings'))

@app.route('/check_user_permission')
@login_required
@cache.cached(timeout=300)
def check_user_permission():
    credentials = get_credentials()
    classroom_service = build('classroom', 'v1', credentials=credentials)

    try:
        user_id = 'me'
        user_profile = classroom_service.userProfiles().get(userId=user_id).execute()
        
        permissions = user_profile.get('permissions', [])

        has_create_course_permission = 'CREATE_COURSE' in permissions
        has_view_course_permission = 'VIEW_COURSE' in permissions
        has_manage_course_permission = 'MANAGE_COURSE' in permissions

        return jsonify({
            'user_id': user_id,
            'has_create_course_permission': has_create_course_permission,
            'has_view_course_permission': has_view_course_permission,
            'has_manage_course_permission': has_manage_course_permission
        })
    except Exception as e:
        logger.error(f"Error checking permissions: {str(e)}")
        return jsonify({'success': False, 'message': f"Error checking permissions: {str(e)}"})

@app.route('/analytics')
@login_required
@cache.cached(timeout=300)
def analytics():
    credentials = get_credentials()
    classroom_service = build('classroom', 'v1', credentials=credentials)

    try:
        courses = classroom_service.courses().list(pageSize=10).execute().get('courses', [])
        analytics_data = []
        total_assignments = 0
        total_submitted = 0
        submission_timeline = {}

        for course in courses:
            course_work = classroom_service.courses().courseWork().list(courseId=course['id']).execute().get('courseWork', [])
            course_assignments = len(course_work)
            submitted_assignments = 0

            for work in course_work:
                submissions = classroom_service.courses().courseWork().studentSubmissions().list(
                    courseId=course['id'],
                    courseWorkId=work['id'],
                    userId='me'
                ).execute().get('studentSubmissions', [])
                
                if submissions and submissions[0]['state'] == 'TURNED_IN':
                    submitted_assignments += 1
                    submission_date = submissions[0]['updateTime'][:10]  # YYYY-MM-DD
                    submission_timeline[submission_date] = submission_timeline.get(submission_date, 0) + 1

            completion_rate = (submitted_assignments / course_assignments) * 100 if course_assignments > 0 else 0

            analytics_data.append({
                'course_name': course['name'],
                'total_assignments': course_assignments,
                'submitted_assignments': submitted_assignments,
                'completion_rate': round(completion_rate, 2)
            })

            total_assignments += course_assignments
            total_submitted += submitted_assignments

        overall_completion_rate = (total_submitted / total_assignments) * 100 if total_assignments > 0 else 0

        # Sort the submission timeline and get the last 30 days
        sorted_timeline = sorted(submission_timeline.items())[-30:]
        submission_dates = [date for date, _ in sorted_timeline]
        submission_counts = [count for _, count in sorted_timeline]

        return render_template('analytics.html', 
                               analytics_data=analytics_data,
                               overall_completion_rate=round(overall_completion_rate, 2),
                               total_courses=len(courses),
                               total_assignments=total_assignments,
                               submission_timeline=submission_dates,
                               submission_counts=submission_counts)
    except Exception as e:
        logger.error(f"Error fetching analytics: {str(e)}")
        return redirect(url_for('error_page', message="Failed to load analytics"))

@app.route('/create_course', methods=['GET', 'POST'])
@login_required
@limiter.limit("3/hour")
def create_course():
    if request.method == 'POST':
        credentials = get_credentials()
        classroom_service = build('classroom', 'v1', credentials=credentials)

        course = {
            'name': request.form.get('name'),
            'section': request.form.get('section'),
            'descriptionHeading': request.form.get('description_heading'),
            'description': request.form.get('description'),
            'room': request.form.get('room'),
            'ownerId': 'me'
        }

        try:
            course = classroom_service.courses().create(body=course).execute()
            flash(f'Course "{course["name"]}" created successfully!', 'success')
            return redirect(url_for('courses'))
        except Exception as e:
            logger.error(f"Error creating course: {str(e)}")
            flash('Failed to create course. Please try again.', 'error')

    return render_template('create_course.html')

@app.errorhandler(RefreshError)
def handle_refresh_error(e):
    session.clear()
    return redirect(url_for('authorize'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, ssl_context='adhoc')