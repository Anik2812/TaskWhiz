from flask import Flask, render_template, request, redirect, url_for, flash
from config import Config
from github import Github
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import schedule
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
app.config.from_object(Config)

# GitHub and Google Classroom API clients
github_client = None
classroom_service = None

def send_email(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = app.config['EMAIL_ADDRESS']
    msg['To'] = app.config['EMAIL_ADDRESS']

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
        smtp_server.login(app.config['EMAIL_ADDRESS'], app.config['EMAIL_PASSWORD'])
        smtp_server.sendmail(app.config['EMAIL_ADDRESS'], app.config['EMAIL_ADDRESS'], msg.as_string())

def check_assignments():
    global github_client, classroom_service
    if not github_client or not classroom_service:
        return

    repo = github_client.get_repo(app.config['GITHUB_REPO'])
    courses = classroom_service.courses().list(pageSize=10).execute()

    for course in courses.get('courses', []):
        course_work = classroom_service.courses().courseWork().list(courseId=course['id']).execute()
        for work in course_work.get('courseWork', []):
            due_date = work.get('dueDate')
            if due_date:
                due_datetime = datetime(year=due_date['year'], month=due_date['month'], day=due_date['day'])
                if due_datetime - datetime.now() <= timedelta(days=1):
                    # Check if the assignment file exists in the GitHub repo
                    try:
                        repo.get_contents(f"{work['title']}/submission.txt")
                    except:
                        send_email(
                            f"Urgent: {work['title']} due soon",
                            f"Your assignment '{work['title']}' is due soon, but the submission file hasn't been uploaded to GitHub yet. Please upload it as soon as possible."
                        )

def run_scheduler():
    schedule.every().day.at("09:00").do(check_assignments)
    while True:
        schedule.run_pending()
        time.sleep(1)

import threading
scheduler_thread = threading.Thread(target=run_scheduler)
scheduler_thread.start()

@app.route('/submit/<assignment_name>', methods=['POST'])
def submit_assignment(assignment_name):
    global github_client, classroom_service
    if not github_client or not classroom_service:
        flash('Error: Not authenticated with GitHub or Google Classroom')
        return redirect(url_for('dashboard'))

    repo = github_client.get_repo(app.config['GITHUB_REPO'])
    file_content = request.files['submission'].read()

    try:
        repo.create_file(f"{assignment_name}/submission.txt", f"Submit {assignment_name}", file_content)
        flash(f'Successfully submitted {assignment_name}')
    except Exception as e:
        flash(f'Error submitting assignment: {str(e)}')

    return redirect(url_for('dashboard'))

@app.route('/')
def index():
    return render_template('index.html')

# Google Classroom API setup
SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students',
    'https://www.googleapis.com/auth/classroom.coursework.me'
]

def get_google_auth_flow():
    flow = Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=SCOPES,
        redirect_uri=app.config['GOOGLE_REDIRECT_URI'])
    return flow

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
    
    global classroom_service
    classroom_service = build('classroom', 'v1', credentials=credentials)
    
    return redirect(url_for('dashboard'))

from github import Github
from googleapiclient.http import MediaIoBaseUpload
import io

@app.route('/dashboard')
def dashboard():
    global github_client, classroom_service
    if not github_client:
        github_client = Github(app.config['GITHUB_TOKEN'])
    
    if not classroom_service:
        return redirect(url_for('authorize'))
    
    repo = github_client.get_repo(app.config['GITHUB_REPO'])
    
    # Fetch courses from Google Classroom
    courses = classroom_service.courses().list(pageSize=10).execute()
    
    for course in courses.get('courses', []):
        course_work = classroom_service.courses().courseWork().list(courseId=course['id']).execute()
        for work in course_work.get('courseWork', []):
            # Check if there's a matching folder in the GitHub repo
            try:
                folder_contents = repo.get_contents(work['title'])
                if folder_contents:
                    # Get the submission file
                    submission_file = next((file for file in folder_contents if file.name == 'submission.txt'), None)
                    if submission_file:
                        # Get the file content
                        file_content = repo.get_contents(submission_file.path).decoded_content
                        
                        # Create a media upload object
                        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='text/plain', resumable=True)
                        
                        # Submit the assignment
                        student_submission = classroom_service.courses().courseWork().studentSubmissions().list(
                            courseId=course['id'],
                            courseWorkId=work['id'],
                            userId='me'
                        ).execute().get('studentSubmissions', [])[0]
                        
                        classroom_service.courses().courseWork().studentSubmissions().turnIn(
                            courseId=course['id'],
                            courseWorkId=work['id'],
                            id=student_submission['id']
                        ).execute()
                        
                        attachment = classroom_service.courses().courseWork().studentSubmissions().attachments().create(
                            courseId=course['id'],
                            courseWorkId=work['id'],
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
                        
                        print(f"Submitted assignment: {work['title']}")
            except Exception as e:
                print(f"Error submitting assignment {work['title']}: {str(e)}")
    
    return "Assignments checked and submitted if applicable."

@app.route('/submit_assignments')
def submit_assignments():
    return dashboard()

if __name__ == '__main__':
    app.run(debug=True, ssl_context='adhoc')