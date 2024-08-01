import json
import os
import logging
import io
import threading
import time
from datetime import datetime, timedelta

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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from config import Config

app = Flask(__name__, static_url_path='/static')
app.config.from_object(Config)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

github_client = None
classroom_service = None
drive_service = None

SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students',
    'https://www.googleapis.com/auth/classroom.rosters.readonly',
    'https://www.googleapis.com/auth/drive.file',
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
]

def get_credentials():
    if 'credentials' not in session:
        return None
    credentials = Credentials(**session['credentials'])
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            session['credentials'] = credentials_to_dict(credentials)
        except:
            return None
    return credentials

def refresh_credentials():
    if 'credentials' not in session:
        return None
    credentials = Credentials(**session['credentials'])
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            session['credentials'] = credentials_to_dict(credentials)
        except Exception as e:
            logger.error(f"Error refreshing credentials: {str(e)}")
            return None
    return credentials

@app.before_request
def before_request():
    if 'credentials' in session:
        refresh_credentials()

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

        # Create a new file in Google Drive
        file_metadata = {'name': filename}
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='text/plain', resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        # Attach the file
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

        # Turn in the assignment
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

def submit_assignment(course_id, course_work_id, filename, file_content):
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

        # Create a new file in Google Drive
        file_metadata = {'name': filename}
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='text/plain', resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        # Attach the file
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

        # Turn in the assignment
        classroom_service.courses().courseWork().studentSubmissions().turnIn(
            courseId=course_id,
            courseWorkId=course_work_id,
            id=student_submission['id']
        ).execute()

        logger.info(f"Successfully submitted assignment: {filename}")
    except HttpError as e:
        error_details = json.loads(e.content.decode('utf-8'))
        logger.error(f"HTTP Error {e.resp.status}: {error_details['error']['message']}")
        raise
    except Exception as e:
        logger.error(f"Error submitting assignment: {str(e)}")
        raise

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
def index():
    return render_template('index.html')

@app.route('/check_auth')
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
def dashboard():
    credentials = get_credentials()
    if not credentials:
        return redirect(url_for('authorize'))
    
    try:
        classroom_service = build('classroom', 'v1', credentials=credentials)
        github_client = Github(app.config['GITHUB_TOKEN'])
        
        repo = github_client.get_repo(app.config['GITHUB_REPO'])
        courses = classroom_service.courses().list(pageSize=10).execute()
        assignments = []

        for course in courses.get('courses', []):
            course_work = classroom_service.courses().courseWork().list(courseId=course['id']).execute()
            for work in course_work.get('courseWork', []):
                due_date = parse_due_date(work.get('dueDate', {}))
                assignment = {
                    'id': work['id'],
                    'title': work['title'],
                    'course': course['name'],
                    'due_date': due_date.strftime('%Y-%m-%d') if due_date else 'No due date',
                    'status': 'Not submitted'
                }
                
                # Check submission status
                submissions = classroom_service.courses().courseWork().studentSubmissions().list(
                    courseId=course['id'],
                    courseWorkId=work['id'],
                    userId='me'
                ).execute().get('studentSubmissions', [])
                
                if submissions and submissions[0]['state'] == 'TURNED_IN':
                    assignment['status'] = 'Submitted'
                else:
                    try:
                        repo.get_contents(f"{work['title']}/submission.txt")
                        assignment['status'] = 'Ready to submit'
                    except GithubException:
                        pass
                
                assignments.append(assignment)
        
        return render_template('dashboard.html', assignments=assignments)
    except Exception as e:
        logger.error(f"Error in dashboard: {str(e)}")
        return redirect(url_for('error_page', message="Failed to load dashboard"))

@app.route('/error')
def error_page():
    error_message = request.args.get('message', 'An unknown error occurred.')
    return render_template('error.html', error_message=error_message)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/submit/<assignment_id>', methods=['POST'])
def submit_assignment_manually(assignment_id):
    if 'credentials' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'})

    credentials = Credentials(**session['credentials'])
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
        
        # Find the correct course and coursework IDs
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
        
        # Submit the assignment
        student_submissions = classroom_service.courses().courseWork().studentSubmissions().list(
            courseId=course_id,
            courseWorkId=course_work_id,
            userId='me'
        ).execute().get('studentSubmissions', [])
        
        if not student_submissions:
            return jsonify({'success': False, 'message': 'No submission found for this assignment'})

        student_submission = student_submissions[0]

        # Create a new file in Google Drive
        file_metadata = {'name': secure_filename(file.filename)}
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='text/plain', resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        # Attach the file
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

        # Turn in the assignment
        classroom_service.courses().courseWork().studentSubmissions().turnIn(
            courseId=course_id,
            courseWorkId=course_work_id,
            id=student_submission['id']
        ).execute()

        return jsonify({'success': True, 'message': 'Assignment submitted successfully'})
    except HttpError as e:
        error_details = json.loads(e.content.decode('utf-8'))
        logger.error(f"HTTP Error {e.resp.status}: {error_details['error']['message']}")
        return jsonify({'success': False, 'message': f"Error submitting assignment: {error_details['error']['message']}"})
    except Exception as e:
        logger.error(f"Error submitting assignment manually: {str(e)}")
        return jsonify({'success': False, 'message': f'Error submitting assignment: {str(e)}'})

@app.route('/revoke')
def revoke():
    if 'credentials' in session:
        credentials = Credentials(**session['credentials'])
        revoke = requests.post('https://oauth2.googleapis.com/revoke',
            params={'token': credentials.token},
            headers = {'content-type': 'application/x-www-form-urlencoded'})
        status_code = getattr(revoke, 'status_code')
        if status_code == 200:
            return redirect(url_for('authorize'))
    return redirect(url_for('index'))

@app.route('/assignments')
def assignments():
    credentials = refresh_credentials()
    if not credentials:
        return redirect(url_for('authorize'))
    
    if not classroom_service:
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
        return redirect(url_for('error_page', message="Failed to load assignments"))

@app.route('/courses')
def courses():
    credentials = refresh_credentials()
    if not credentials:
        return redirect(url_for('authorize'))
    
    if not classroom_service:
        classroom_service = build('classroom', 'v1', credentials=credentials)
    
    try:
        courses = classroom_service.courses().list(pageSize=10).execute()
        return render_template('courses.html', courses=courses.get('courses', []))
    except Exception as e:
        logger.error(f"Error fetching courses: {str(e)}")
        return redirect(url_for('error_page', message="Failed to load courses"))

@app.route('/profile')
def profile():
    credentials = refresh_credentials()
    if not credentials:
        return redirect(url_for('authorize'))
    
    try:
        user_info_service = build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()
        return render_template('profile.html', user_info=user_info)
    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}")
        return redirect(url_for('error_page', message="Failed to load user profile"))

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/update_settings', methods=['POST'])
def update_settings():
    # Here you can add logic to update user settings
    # For example, updating email preferences, GitHub token, etc.
    flash('Settings updated successfully', 'success')
    return redirect(url_for('settings'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, ssl_context='adhoc')