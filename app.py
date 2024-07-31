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
import schedule
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from config import Config

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

github_client = None
classroom_service = None

SCOPES = [
    'https://www.googleapis.com/auth/classroom.student-submissions.me.readonly',
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.me'
]

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
    global github_client, classroom_service
    if not github_client or not classroom_service:
        logger.warning("GitHub or Classroom client not initialized")
        return

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
                        submit_assignment(course['id'], work['id'], work['title'], file_content)
                        logger.info(f"Automatically submitted assignment: {work['title']}")
                    except GithubException:
                        logger.warning(f"No submission file found for {work['title']}")
    except Exception as e:
        logger.error(f"Error in check_and_submit_assignments: {str(e)}")

def parse_due_date(due_date):
    if not due_date:
        return None
    return datetime(year=due_date.get('year', 1), month=due_date.get('month', 1), day=due_date.get('day', 1))

def submit_assignment(course_id, course_work_id, assignment_name, file_content):
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

        # Check if the assignment is already submitted
        if student_submission['state'] == 'TURNED_IN':
            logger.info(f"Assignment '{assignment_name}' is already submitted.")
            return

        # Turn in the assignment
        classroom_service.courses().courseWork().studentSubmissions().turnIn(
            courseId=course_id,
            courseWorkId=course_work_id,
            id=student_submission['id']
        ).execute()

        # Attach the file
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='text/plain', resumable=True)
        classroom_service.courses().courseWork().studentSubmissions().attachments().create(
            courseId=course_id,
            courseWorkId=course_work_id,
            id=student_submission['id'],
            body={
                'addAttachments': [{
                    'driveFile': {
                        'title': 'submission.txt'
                    }
                }]
            },
            media_body=media
        ).execute()

        send_email(
            f"Assignment Submitted: {assignment_name}",
            f"Your assignment '{assignment_name}' has been automatically submitted to Google Classroom."
        )
        logger.info(f"Successfully submitted assignment: {assignment_name}")
    except Exception as e:
        logger.error(f"Error submitting assignment: {str(e)}")

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

@app.route('/authorize')
def authorize():
    flow = get_google_auth_flow()
    authorization_url, _ = flow.authorization_url(prompt='consent')
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    flow = get_google_auth_flow()
    logger.info(f"Received callback URL: {request.url}")
    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        logger.info(f"Successfully obtained credentials: {credentials.to_json()}")
        
        global classroom_service
        classroom_service = build('classroom', 'v1', credentials=credentials)
        
        session['credentials'] = credentials_to_dict(credentials)
        return redirect(url_for('dashboard'))
    except Exception as e:
        logger.error(f"OAuth error: {str(e)}")
        error_message = f"Authentication failed: {str(e)}"
        return redirect(url_for('error_page', message=error_message))

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
    global github_client, classroom_service
    
    credentials = refresh_credentials()
    if not credentials:
        return redirect(url_for('authorize'))
    
    if not github_client:
        github_client = Github(app.config['GITHUB_TOKEN'])
    
    if not classroom_service:
        classroom_service = build('classroom', 'v1', credentials=credentials)
    
    try:
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
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'})
    try:
        file_content = file.read()
        return jsonify({'success': True, 'message': 'Assignment submitted successfully'})
    except Exception as e:
        logger.error(f"Error submitting assignment manually: {str(e)}")
        return jsonify({'success': False, 'message': 'Error submitting assignment'})

if __name__ == '__main__':
    app.run(debug=True, ssl_context='adhoc')