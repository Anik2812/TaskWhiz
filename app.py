import json
import os
import logging
import io
import threading
import time
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from github import Github
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import schedule
import smtplib
from email.mime.text import MIMEText

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load configuration
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

# GitHub and Google Classroom API clients
github_client = None
classroom_service = None

# Google Classroom API setup
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
                try:
                    file_content = repo.get_contents(f"{work['title']}/submission.txt").decoded_content
                    submit_assignment(course['id'], work['id'], work['title'], file_content)
                    logger.info(f"Submitted assignment: {work['title']}")
                except Exception as e:
                    logger.error(f"Error submitting assignment {work['title']}: {str(e)}")
    except Exception as e:
        logger.error(f"Error in check_and_submit_assignments: {str(e)}")

def submit_assignment(course_id, course_work_id, assignment_name, file_content):
    student_submission = classroom_service.courses().courseWork().studentSubmissions().list(
        courseId=course_id,
        courseWorkId=course_work_id,
        userId='me'
    ).execute().get('studentSubmissions', [])[0]

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
                assignment = {
                    'title': work['title'],
                    'course': course['name'],
                    'due_date': work.get('dueDate', 'No due date'),
                    'status': 'Not submitted'
                }
                
                try:
                    repo.get_contents(f"{work['title']}/submission.txt")
                    assignment['status'] = 'Ready to submit'
                except:
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

if __name__ == '__main__':
    app.run(debug=False, ssl_context='adhoc')