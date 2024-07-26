import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
    GITHUB_REPO = os.environ.get('GITHUB_REPO')
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI')
    EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
    EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')