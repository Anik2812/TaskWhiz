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
import os

app = Flask(__name__)
app.config.from_object(Config)

# GitHub and Google Classroom API clients
github_client = None
classroom_service = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    # Fetch assignments from GitHub and Google Classroom
    assignments = []
    return render_template('dashboard.html', assignments=assignments)

if __name__ == '__main__':
    app.run(debug=True)