# PythonAnywhere Deployment Guide - Civic Portal

This guide explains how to deploy the Civic Portal Flask application on PythonAnywhere.

## Quick Setup Steps

### 1. Upload Your Project
- Upload the entire project folder to PythonAnywhere via the file browser or Git

### 2. Create a Virtual Environment
```bash
mkvirtualenv --python=/usr/bin/python3.10 civicportal
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
In the PythonAnywhere Web app settings, set the following environment variables:

1. Go to **Web** > **Edit configuration file** (or your web app settings)
2. Add these environment variables:

```
SECRET_KEY=your-secure-random-key-here
GEMINI_API_KEY=your-gemini-api-key-here
FLASK_DEBUG=False
```

**To generate a secure SECRET_KEY**, run:
```python
import secrets
print(secrets.token_hex(32))
```

### 5. Configure WSGI File
- In PythonAnywhere Web app settings, set the WSGI configuration file to:
```
/home/yourusername/civicportal/wsgi.py
```

### 6. Set Python Version
- Ensure Python 3.10+ is selected in your Web app settings

### 7. Create Database
Before first access, initialize the database:
```bash
python
>>> from app import app, db
>>> with app.app_context():
>>>     db.create_all()
>>> exit()
```

### 8. Reload Web App
- Click "Reload" on your Web app in PythonAnywhere

## Important Notes

### Database Location
- The SQLite database is stored in the `instance/` folder
- On PythonAnywhere, this folder is automatically created and persisted

### Static Files
- Static files (CSS, JavaScript, images) are served from the `static/` folder
- Configure static file mapping in Web app settings:
  - URL: `/static/`
  - Directory: `/home/yourusername/civicportal/static`

### Uploads
- Uploaded files go to `static/uploads/`
- Make sure the directory has write permissions

### Security Considerations
✓ API keys are now loaded from environment variables (not hardcoded)
✓ Secret key should be changed from default
✓ Debug mode is off in production
✓ Database uses SQLite - consider upgrading to MySQL for production scale

## Troubleshooting

**"ModuleNotFoundError: No module named 'google'"**
- Run: `pip install google-generative-ai`

**Database locked errors**
- PythonAnywhere defaults to SQLite which has limited concurrency
- For production, upgrade to MySQL or PostgreSQL

**Static files not loading**
- Configure static file mappings in Web app settings
- Clear browser cache

**API key errors**
- Verify GEMINI_API_KEY is set in environment variables
- Check the Web app settings - Log in to verify it's configured

## Moving to Production Database

For higher traffic, update DATABASE_URL environment variable:

```
# PostgreSQL
DATABASE_URL=postgresql://user:password@host/dbname

# MySQL
DATABASE_URL=mysql+pymysql://user:password@host/dbname
```

Then update the SQLAlchemy connection string in `app.py`.

## File Structure
```
civicportal/
├── app.py                 # Main Flask application
├── wsgi.py               # WSGI entry point for PythonAnywhere
├── requirements.txt      # Python dependencies
├── instance/             # Instance-specific files (DB, config)
├── static/              # Static files (CSS, JS, images, uploads)
├── templates/           # HTML templates
└── this file            # Deployment guide
```
