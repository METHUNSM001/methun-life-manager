# LIFE MANAGER - Deployment Guide

## Prerequisites
- GitHub account (create at https://github.com)
- Vercel account (create at https://vercel.com)
- Git installed (https://git-scm.com)

---

## Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Create a new repository with name: `life-manager`
3. Do NOT initialize with README, .gitignore, or license (we already have these)
4. Click "Create repository"
5. Copy the repository URL (will be something like: `https://github.com/YOUR_USERNAME/life-manager.git`)

---

## Step 2: Push Code to GitHub

Run these commands in the project directory:

```bash
# Configure git (first time only)
git config user.name "Your Name"
git config user.email "your.email@gmail.com"

# Check git status
git status

# Add all files
git add .

# Commit changes
git commit -m "Initial commit: LIFE MANAGER Flask app with AI features"

# Add remote repository (replace with your GitHub URL)
git remote add origin https://github.com/YOUR_USERNAME/life-manager.git

# Push to GitHub
git branch -M main
git push -u origin main
```

---

## Step 3: Configure Vercel Deployment

### Environment Variables (IMPORTANT!)

1. Go to https://vercel.com
2. Sign in with GitHub
3. Click "New Project"
4. Select "Import Git Repository"
5. Find and import your `life-manager` repository

### Set Environment Variables:

In Vercel project settings, go to **Settings > Environment Variables** and add:

```
GROQ_API_KEY = your_groq_api_key_here
```

IMPORTANT: Use your own Groq API key from https://console.groq.com/keys

### Framework & Build Settings:

Vercel should auto-detect Python. Make sure:
- **Framework**: Python
- **Build Command**: Leave empty (default)
- **Output Directory**: api
- **Development Command**: `python app.py`

---

## Step 4: Deploy

1. Click "Deploy" button in Vercel
2. Wait for deployment to complete (usually 1-2 minutes)
3. You'll get a deployment URL like: `https://life-manager-abc123.vercel.app`

---

## Step 5: Verify Deployment

1. Visit your deployment URL
2. Test login/register functionality
3. Test all features (Teacher, Health, Diet, Crop)

---

## Important Security Notes

⚠️ **URGENT**: Before deploying with your API key:

1. **Remove hardcoded API key** from `app.py` line 18:
   ```python
   # DO NOT hardcode in production!
   GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Use environment variable only
   ```

2. **Rotate your API key** on Groq dashboard after deploying

3. **Use a strong secret key** in app.py (line 15):
   ```python
   app.secret_key = os.getenv("SECRET_KEY", "change-this-to-random-string")
   ```

---

## Troubleshooting

### Build fails with "Python version not supported"
- Add `runtime.txt` in root with content: `python-3.11`

### Database/Excel file not persisting
- Vercel has ephemeral storage. Consider:
  - Moving to DBaaS (e.g., MongoDB, PostgreSQL)
  - Using Vercel KV for session storage

### GROQ API errors on Vercel
- Verify `GROQ_API_KEY` is set in Environment Variables
- Check API key is valid and active

### Module import errors
- Ensure `requirements.txt` has all dependencies
- Run: `pip install -r requirements.txt` locally to verify

---

## Continuous Deployment

After setup, every `git push` to `main` branch will:
1. Trigger Vercel to pull latest code
2. Automatically build and deploy
3. Fail if build errors occur

No need to manually redeploy!

---

## Monitoring & Updates

- View logs: Vercel Dashboard > Deployments > Select Deploy > Logs
- Rollback: Vercel Dashboard > Deployments > Click 3-dots > Rollback
- Domain: Add custom domain in Vercel > Settings > Domains

---

## Questions?

- Vercel Docs: https://vercel.com/docs
- Flask Deployment: https://flask.palletsprojects.com/deployment/
- GitHub: https://docs.github.com/
