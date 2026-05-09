# 📋 Gmail OAuth Setup - Step by Step

## Step 1: Download Your credentials.json

### From Google Cloud Console:

1. Go to: https://console.cloud.google.com/
2. Select your Project
3. Go to **APIs & Services** → **Credentials**
4. Find your **OAuth 2.0 Client ID** (should show "Desktop application")
5. Click the **Download button** (⬇️ icon) on the right
6. This downloads your `credentials.json` file

---

## Step 2: Create the Folder

**Path:** `d:\AI-email-test\AI-Project\email_send\email_credentials\`

### Do this:

1. Open File Explorer
2. Navigate to: `d:\AI-email-test\AI-Project\email_send\`
3. Create new folder: `email_credentials`
4. Your folder path should be: `d:\AI-email-test\AI-Project\email_send\email_credentials\`

---

## Step 3: Place credentials.json

1. Take the `credentials.json` you downloaded
2. Move/Copy it to: `d:\AI-email-test\AI-Project\email_send\email_credentials\credentials.json`

**Your final path should be:**

```
d:\AI-email-test\AI-Project\email_send\email_credentials\credentials.json
```

---

## Step 4: First Time Authentication

1. Open Streamlit app: http://localhost:8501
2. Go to **⚙️ Settings** tab
3. Under "🔐 Gmail Authentication", click **"🔓 Authenticate with Gmail"**
4. Browser will open
5. Select your Google account
6. Click **Allow** to grant permissions
7. ✅ Done! Token saved automatically

---

## What if you ONLY have Client ID & Secret?

If you can see the Client ID and Secret in Google Cloud Console:

### Option A: Download JSON (Recommended)

- Follow steps above to download `credentials.json`

### Option B: Create Manually

If you can't download, create file `d:\AI-email-test\AI-Project\email_send\email_credentials\credentials.json`:

```json
{
  "installed": {
    "client_id": "YOUR-CLIENT-ID-HERE.apps.googleusercontent.com",
    "project_id": "your-project-name",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "YOUR-CLIENT-SECRET-HERE",
    "redirect_uris": ["http://localhost:8080/"]
  }
}
```

Replace:

- `YOUR-CLIENT-ID-HERE` with your Client ID
- `YOUR-CLIENT-SECRET-HERE` with your Client Secret

---

## Fix Error 400: redirect_uri_mismatch

If Google shows `redirect_uri_mismatch`, your OAuth client does not allow the callback URL used by this local app.

Best fix: create a new OAuth Client ID with **Application type: Desktop app**, download the JSON, and place it at:

```
d:\AI-email-test\AI-Project\email_send\email_credentials\credentials.json
```

If you keep using a **Web application** OAuth client, open that client in Google Cloud Console and add this exact value under **Authorized redirect URIs**:

```
http://localhost:8080/
```

Download the updated JSON again after saving.

---

## ✅ After Setup:

The app will:

1. Load `credentials.json` automatically
2. On first use, open browser for OAuth login
3. Save token in: `email_send/email_credentials/token.pickle`
4. Use saved token for future emails (no re-login needed)

---

## 🎯 Quick Checklist

- [ ] Downloaded `credentials.json` from Google Cloud
- [ ] Created folder: `email_send\email_credentials`
- [ ] Placed `credentials.json` in: `d:\AI-email-test\AI-Project\email_send\email_credentials\credentials.json`
- [ ] Streamlit app running on http://localhost:8501
- [ ] Go to Settings tab
- [ ] Click "Authenticate with Gmail"
- [ ] Login in browser
- [ ] ✅ Ready to send emails!

---

## Need Help?

**Streamlit app is already running at:** http://localhost:8501

**Next action:**

1. Get your `credentials.json` (download or create it)
2. Place in the `email_send\email_credentials` folder
3. Go to Settings → Click Authenticate
4. Done!
