# FreightFlow Tariff App - Deployment Guide

## 🚀 Deploy to Railway.app (Recommended)

### Prerequisites
- GitHub account
- Railway account (sign up at https://railway.app)
- Gemini API key

### Step-by-Step Deployment

#### 1. Prepare Your Repository
```bash
# Initialize git if not already done
git init
git add .
git commit -m "Initial commit"

# Push to GitHub
git remote add origin <your-github-repo-url>
git push -u origin main
```

#### 2. Deploy on Railway

1. **Go to Railway**: https://railway.app
2. **Click "New Project"**
3. **Select "Deploy from GitHub repo"**
4. **Choose your repository**: `freightflow-tariff-app`
5. **Railway will auto-detect** the Python app

#### 3. Add PostgreSQL Database

1. **In your Railway project**, click "New"
2. **Select "Database" → "PostgreSQL"**
3. **Railway will create** a PostgreSQL database
4. **Environment variable** `DATABASE_URL` will be auto-added

#### 4. Configure Environment Variables

In Railway dashboard, go to **Variables** and add:

```
GEMINI_API_KEY=your_gemini_api_key_here
```

#### 5. Deploy!

- Railway will automatically build and deploy
- You'll get a URL like: `https://your-app.railway.app`

#### 6. Initialize Database (First Time Only)

After deployment, run extraction to populate the database:

```bash
# Use the Railway URL
curl -X POST https://your-app.railway.app/api/v1/extract_full \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.ups.com/assets/resources/webcontent/en_GB/tariff-guide-in.pdf", "force_refresh": true}'
```

Or visit: `https://your-app.railway.app` and click "Extract Full (Force Refresh)"

---

## 🔧 Alternative: Deploy to Render.com

### Steps:

1. **Go to Render**: https://render.com
2. **New → Web Service**
3. **Connect GitHub repo**
4. **Configure**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. **Add PostgreSQL**: New → PostgreSQL
6. **Add Environment Variables**:
   - `GEMINI_API_KEY`
   - `DATABASE_URL` (auto-added by Render)
7. **Deploy!**

---

## 🐳 Alternative: Deploy with Docker

### Build and Run Locally:
```bash
docker build -t freightflow-api .
docker run -p 8000:8000 -e GEMINI_API_KEY=your_key freightflow-api
```

### Deploy to Google Cloud Run:
```bash
# Build and push
gcloud builds submit --tag gcr.io/YOUR_PROJECT/freightflow-api

# Deploy
gcloud run deploy freightflow-api \
  --image gcr.io/YOUR_PROJECT/freightflow-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_key
```

---

## 📊 Post-Deployment

### Test Your API:
```bash
# Health check
curl https://your-app.railway.app/

# Get data
curl https://your-app.railway.app/api/v1/data
```

### Monitor:
- Railway provides logs and metrics in the dashboard
- Check for errors in the Logs tab

---

## 🔐 Security Notes

1. **Never commit** `.env` file with API keys
2. **Use environment variables** for all secrets
3. **Enable CORS** only for your frontend domain (if needed)
4. **Consider rate limiting** for production use

---

## 💰 Cost Estimates

- **Railway**: Free tier (500 hrs/month) or ~$5/month
- **Render**: Free tier available, paid starts at $7/month
- **Google Cloud Run**: Pay-as-you-go, typically <$5/month for low traffic
- **DigitalOcean**: $5/month minimum

---

## 🆘 Troubleshooting

### Database Connection Issues:
- Ensure `DATABASE_URL` is set correctly
- Check database is running in Railway/Render dashboard

### Port Binding Issues:
- Make sure using `--port $PORT` (Railway/Render set this automatically)

### Module Not Found:
- Verify `requirements.txt` is complete
- Check build logs in Railway/Render

---

## 📝 Next Steps

1. Set up custom domain (optional)
2. Add monitoring (Sentry, LogRocket)
3. Set up CI/CD for automatic deployments
4. Add API authentication if needed
