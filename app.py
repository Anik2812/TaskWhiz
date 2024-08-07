import json
import os
import logging
import io
import threading
import time
import schedule
import smtplib
import requests
from sqlalchemy import func
import functools
from functools import wraps, partial
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from github import Github, GithubException
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError
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
from flask_login import LoginManager, current_user, login_user, logout_user, login_required, UserMixin
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from requests.exceptions import Timeout


# Enhanced logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
logger = logging.getLogger(__name__)

from config import Config

app = Flask(__name__, static_url_path='/static')
CORS(app, resources={r"/*": {"origins": "*"}})
csp = {
    'default-src': ['\'self\'', 'https://fonts.googleapis.com', 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'],
    'script-src': ['\'self\'', 'https://cdnjs.cloudflare.com', 'https://cdn.jsdelivr.net', 'https://cdn.datatables.net', 'https://code.jquery.com', '\'unsafe-inline\''],
    'style-src': ['\'self\'', 'https://fonts.googleapis.com', 'https://cdnjs.cloudflare.com', 'https://cdn.datatables.net', '\'unsafe-inline\''],
    'font-src': ['\'self\'', 'https://fonts.gstatic.com', 'https://cdnjs.cloudflare.com'],
}

Talisman(app, content_security_policy=csp)

app.config.from_object(Config)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

# Setup caching
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Setup rate limiting
limiter = Limiter(key_func=get_remote_address)
limiter.init_app(app)

# Setup database connection
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///taskwhiz.db'
db = SQLAlchemy(app)

migrate = Migrate(app, db)


# User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    settings = db.Column(db.JSON)
    assignments = db.relationship('Assignment', backref='user', lazy=True)
    courses = db.relationship('Course', backref='user', lazy=True)

    def get_id(self):
        return str(self.id)

# Assignment model
class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    status = db.Column(db.String(20))
    file_url = db.Column(db.String(200))
    grade = db.Column(db.Float)
    total_marks = db.Column(db.Float)
    feedback = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    submitted_date = db.Column(db.DateTime)


# Course model
class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    assignments = db.relationship('Assignment', backref='course', lazy=True)

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

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'authorize'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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
    if current_user.is_authenticated and 'credentials' in session:
        credentials = Credentials(**session['credentials'])
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                session['credentials'] = credentials_to_dict(credentials)
            except RefreshError:
                logout_user()
                session.clear()
                flash("Your session has expired. Please log in again.", "error")
                return redirect(url_for('authorize'))

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

    # Get user info and log in the user
    user_info_service = build('oauth2', 'v2', credentials=credentials)
    user_info = user_info_service.userinfo().get().execute()
    email = user_info['email']

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email)
        db.session.add(user)
        db.session.commit()

    login_user(user)
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
@login_required
def logout():
    logout_user()
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
        courses_result = classroom_service.courses().list(pageSize=10).execute()
        courses = courses_result.get('courses', [])

        all_assignments = []
        for course in courses:
            course_work = classroom_service.courses().courseWork().list(courseId=course['id']).execute()
            for work in course_work.get('courseWork', []):
                due_date = parse_due_date(work.get('dueDate', {}))
                
                submissions = classroom_service.courses().courseWork().studentSubmissions().list(
                    courseId=course['id'],
                    courseWorkId=work['id'],
                    userId='me'
                ).execute().get('studentSubmissions', [])
                
                status = 'Not Submitted'
                grade = None
                if submissions:
                    state = submissions[0]['state']
                    if state == 'TURNED_IN':
                        status = 'Submitted'
                    elif state == 'RETURNED':
                        status = 'Graded'
                        grade = submissions[0].get('assignedGrade')

                assignment = {
                    'id': work['id'],
                    'title': work['title'],
                    'course': course['name'],
                    'due_date': due_date.strftime('%Y-%m-%d') if due_date else 'No due date',
                    'description': work.get('description', 'No description available'),
                    'status': status,
                    'grade': grade,
                    'total_marks': work.get('maxPoints', 'N/A')
                }
                all_assignments.append(assignment)
        
        logger.info(f"Fetched {len(all_assignments)} assignments successfully")
        return render_template('assignments.html', assignments=all_assignments, courses=courses)
    except Exception as e:
        logger.error(f"Error in assignments route: {str(e)}", exc_info=True)
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

@app.route('/create_course', methods=['POST'])
@login_required
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

@app.route('/get_analytics_data')
@login_required
def fetch_analytics_data():
    credentials = get_credentials()
    if not credentials:
        logger.error("No valid credentials found")
        raise Exception("No valid credentials found")

    classroom_service = build('classroom', 'v1', credentials=credentials)
    
    try:
        courses_result = classroom_service.courses().list(pageSize=10).execute()
        courses = courses_result.get('courses', [])
        
        logger.info(f"Fetched {len(courses)} courses")

        all_assignments = []
        submission_timeline = {}
        grade_distribution = [0] * 13  # A+, A, A-, B+, B, B-, C+, C, C-, D+, D, D-, F
        workload_distribution = [0] * 7  # Mon to Sun

        for course in courses:
            try:
                course_work = classroom_service.courses().courseWork().list(courseId=course['id'], pageSize=20).execute()
                assignments = course_work.get('courseWork', [])
                
                logger.info(f"Fetched {len(assignments)} assignments for course {course['name']}")

                for work in assignments:
                    due_date = parse_due_date(work.get('dueDate', {}))
                    
                    try:
                        submissions = classroom_service.courses().courseWork().studentSubmissions().list(
                            courseId=course['id'],
                            courseWorkId=work['id'],
                            userId='me'
                        ).execute().get('studentSubmissions', [])
                        
                        if submissions:
                            submission = submissions[0]
                            submitted_date = parse_date(submission.get('creationTime'))
                            
                            if submitted_date:
                                date_key = submitted_date.strftime('%Y-%m-%d')
                                submission_timeline[date_key] = submission_timeline.get(date_key, 0) + 1
                            
                            if due_date:
                                workload_distribution[due_date.weekday()] += 1

                            if 'assignedGrade' in submission:
                                grade = int(submission['assignedGrade'])
                                max_points = int(work.get('maxPoints', 100))
                                grade_percentage = (grade / max_points) * 100

                                if grade_percentage >= 97:
                                    grade_distribution[0] += 1  # A+
                                elif grade_percentage >= 93:
                                    grade_distribution[1] += 1  # A
                                elif grade_percentage >= 90:
                                    grade_distribution[2] += 1  # A-
                                elif grade_percentage >= 87:
                                    grade_distribution[3] += 1  # B+
                                elif grade_percentage >= 83:
                                    grade_distribution[4] += 1  # B
                                elif grade_percentage >= 80:
                                    grade_distribution[5] += 1  # B-
                                elif grade_percentage >= 77:
                                    grade_distribution[6] += 1  # C+
                                elif grade_percentage >= 73:
                                    grade_distribution[7] += 1  # C
                                elif grade_percentage >= 70:
                                    grade_distribution[8] += 1  # C-
                                elif grade_percentage >= 67:
                                    grade_distribution[9] += 1  # D+
                                elif grade_percentage >= 63:
                                    grade_distribution[10] += 1  # D
                                elif grade_percentage >= 60:
                                    grade_distribution[11] += 1  # D-
                                else:
                                    grade_distribution[12] += 1  # F
                        
                        all_assignments.append({
                            'id': work['id'],
                            'title': work['title'],
                            'course': course['name'],
                            'due_date': due_date.strftime('%Y-%m-%d') if due_date else 'No due date',
                            'status': submission['state'] if submissions else 'Not submitted',
                            'grade': submission.get('assignedGrade', 'Not graded') if submissions else 'Not graded'
                        })
                    except HttpError as e:
                        logger.error(f"Error fetching submissions for assignment {work['id']}: {str(e)}")
                        continue
                    except Exception as e:
                        logger.error(f"Unexpected error processing assignment {work['id']}: {str(e)}")
                        continue

            except HttpError as e:
                logger.error(f"Error fetching assignments for course {course['name']}: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error processing course {course['name']}: {str(e)}")
                continue

        total_assignments = len(all_assignments)
        completed_assignments = sum(1 for a in all_assignments if a['status'] in ['TURNED_IN', 'RETURNED'])
        overall_completion_rate = (completed_assignments / total_assignments * 100) if total_assignments > 0 else 0
        
        graded_assignments = [a for a in all_assignments if a['grade'] != 'Not graded']
        average_grade = sum(float(a['grade']) for a in graded_assignments) / len(graded_assignments) if graded_assignments else 0

        course_analytics = []
        for course in courses:
            course_assignments = [a for a in all_assignments if a['course'] == course['name']]
            total_course_assignments = len(course_assignments)
            completed_course_assignments = sum(1 for a in course_assignments if a['status'] in ['TURNED_IN', 'RETURNED'])
            completion_rate = (completed_course_assignments / total_course_assignments * 100) if total_course_assignments > 0 else 0
            
            graded_course_assignments = [a for a in course_assignments if a['grade'] != 'Not graded']
            average_course_grade = sum(float(a['grade']) for a in graded_course_assignments) / len(graded_course_assignments) if graded_course_assignments else 0
            
            course_analytics.append({
                'course_name': course['name'],
                'total_assignments': total_course_assignments,
                'submitted_assignments': completed_course_assignments,
                'completion_rate': completion_rate,
                'average_grade': average_course_grade
            })

        return {
            'total_courses': len(courses),
            'total_assignments': total_assignments,
            'overall_completion_rate': overall_completion_rate,
            'average_grade': average_grade,
            'submission_timeline': dict(sorted(submission_timeline.items())),
            'grade_distribution': grade_distribution,
            'workload_distribution': workload_distribution,
            'course_analytics': course_analytics
        }

    except Timeout:
        logger.error("Request to Google Classroom API timed out")
        raise Exception("Request to Google Classroom API timed out. Please try again later.")
    except HttpError as e:
        logger.error(f"HTTP Error in fetch_analytics_data: {e}")
        raise Exception(f"Failed to fetch data from Google Classroom API: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in fetch_analytics_data: {str(e)}")
        raise Exception(f"An unexpected error occurred: {str(e)}")

def parse_due_date(due_date):
    if not due_date:
        return None
    return datetime(year=due_date.get('year', 1), month=due_date.get('month', 1), day=due_date.get('day', 1))

def parse_date(date_string):
    if not date_string:
        return None
    return datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S.%fZ")

@app.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html')   
        

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Unhandled exception: {str(e)}")
    return jsonify({'error': 'An unexpected error occurred'}), 500

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