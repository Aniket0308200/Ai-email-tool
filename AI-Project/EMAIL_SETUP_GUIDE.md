# 📧 Email Functionality Setup Guide

## Overview

This guide explains how to set up and use the email functionality integrated into your AI chatbot.

---

## 📋 Architecture

### Email Workflow: Direct Send

```
User Input → Intent Detection → Entity Extraction → LLM Composition → Gmail Send
```

### Components

#### 1. **gmail_handler.py** - Gmail API Integration

- OAuth2 authentication with Gmail
- Secure token storage (pickle format)
- Email sending via Gmail API
- Credentials management

#### 2. **intent_parser.py** - Intent & Entity Recognition

- Detects "send email" intent from user input
- Extracts recipient (name or email)
- Extracts email topic/subject context
- Determines email tone (professional, formal, casual, friendly)

#### 3. **email_composer.py** - LLM-Based Email Generation

- Uses DeepSeek LLM to generate professional emails
- Creates subject lines and email bodies
- Validates email addresses
- Resolves recipient names to email addresses

#### 4. **contacts_manager.py** - Contact Management

- Store and manage email contacts
- Search contacts by name or email
- Persistent storage (JSON format)

#### 5. **app.py** - Streamlit UI

- Chat interface (existing)
- Email composition tab (new)
- Settings tab (new)
- Contact management UI (new)

---

## 🔐 Gmail Authentication Setup

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Create Project**
3. Name your project (e.g., "AI Email Assistant")
4. Click **Create**

### Step 2: Enable Gmail API

1. In the Cloud Console, search for **Gmail API**
2. Click **Gmail API**
3. Click **Enable**

### Step 3: Create OAuth 2.0 Credentials

1. Go to **Credentials** in the left menu
2. Click **Create Credentials** → **OAuth client ID**
3. Select **Desktop application**
4. Click **Create**
5. Download the credentials file

### Step 4: Configure Credentials

1. In your project folder, create: `email_credentials/credentials.json`
2. Paste the downloaded credentials JSON into this file

### Step 5: First Run Authentication

1. On first app run, go to **Settings** tab
2. Click **🔓 Authenticate with Gmail**
3. A browser window will open with Gmail login
4. Grant permission to the app
5. Success! Token will be saved for future use

---

## 📧 How to Send Email

### Via Streamlit UI

#### Step 1: Open Email Tab

- Click the **📧 Email** tab in the app

#### Step 2: Fill Email Details

- **Recipient**: Email address or saved contact name
- **Email Topic**: What the email is about (e.g., "Project Update")
- **Email Tone**: Choose from Professional, Formal, Casual, or Friendly
- **Additional Context** (optional): Any specific points to include

#### Step 3: Generate Email

- Click **✨ Generate Email**
- AI will create a professional subject and body

#### Step 4: Review & Send

- Review the generated email in the preview
- Click **📤 Send Email** to deliver

---

## 📇 Contact Management

### Save a Contact

1. Go to **⚙️ Settings** tab
2. Under **📇 Contacts Management**, fill:
   - **Contact name**: (e.g., "Rahul")
   - **Email address**: (e.g., "rahul@example.com")
3. Click **➕ Add Contact**

### Use Saved Contacts

- In Email tab, click contact quick button
- Automatically fills recipient field
- Or type contact name in recipient field

### Delete a Contact

- Go to **⚙️ Settings** tab
- Find contact in saved list
- Click **🗑️** to remove

---

## 💡 Example Usage

### Example 1: Send Project Update

```
User: "Send email to Rahul about project update"

System extracts:
- Recipient: "Rahul"
- Topic: "project update"
- Tone: "professional" (default)

AI generates:
Subject: "Project Status Update"
Body: Professional update message...

Sent via Gmail to: rahul@example.com
```

### Example 2: Send with Custom Tone

```
User: "Send friendly email to manager@company.com about team feedback"

System extracts:
- Recipient: "manager@company.com"
- Topic: "team feedback"
- Tone: "friendly"

AI generates:
Subject: "Team Feedback & Insights"
Body: Friendly, warm message...

Sent successfully ✅
```

---

## 📁 File Structure

```
AI-Project/
├── app.py                      # Main Streamlit app
├── gmail_handler.py            # Gmail API integration
├── intent_parser.py            # Intent/entity extraction
├── email_composer.py           # LLM email generation
├── contacts_manager.py         # Contact management
├── requirements.txt            # Dependencies
├── contacts.json              # Saved contacts (auto-generated)
└── email_credentials/
    ├── credentials.json        # OAuth 2.0 credentials
    └── token.pickle           # Saved auth token
```

---

## 🔧 Configuration

### Change AI Model

Edit `app.py` sidebar:

```python
selected_model = st.selectbox(
    "Model",
    ["deepseek-r1:1.5b", "deepseek-r1:3b"],  # Edit here
    index=0,
    label_visibility="collapsed",
)
```

### Change Ollama URL

In `email_composer.py`:

```python
OLLAMA_BASE_URL = "http://localhost:11434"  # Change if needed
```

### Email Tone Customization

In `email_composer.py`, update the `tone_description` dictionary to add more tone options.

---

## ✅ Testing Checklist

- [ ] Gmail OAuth2 authentication working
- [ ] Can generate email without sending
- [ ] Email preview shows correct subject and body
- [ ] Can send email to real email address
- [ ] Emails arrive in recipient inbox
- [ ] Can save and recall contacts
- [ ] Different email tones work correctly
- [ ] Intent parser recognizes email requests
- [ ] Chat tab still functions normally

---

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'google.auth'"

- Solution: Reinstall packages: `pip install -r requirements.txt`

### "Gmail authentication failed"

- Ensure `email_credentials/credentials.json` exists
- Regenerate credentials from Google Cloud Console
- Clear saved token: Delete `email_credentials/token.pickle`

### "Invalid email address"

- Check recipient email format: `name@domain.com`
- Ensure contact email is saved correctly

### "Email not sending"

- Verify Gmail account is authenticated
- Check email address validity
- Ensure Ollama is running for email generation
- Check internet connection

### "Generated email quality is poor"

- Try different tone settings
- Provide more detailed subject context
- Use additional context field for specific details

---

## 📚 API Reference

### gmail_handler.py

```python
# Authenticate with Gmail
authenticate_gmail()  # Returns service object

# Send email
send_email(
    to_email="user@example.com",
    subject="Email Subject",
    body="Email body text",
    html=False  # Set True for HTML emails
)  # Returns: {"success": bool, "message": str, ...}

# Check authentication status
is_gmail_authenticated()  # Returns: bool

# Get authenticated email
get_authenticated_email()  # Returns: email string or None

# Clear authentication
clear_authentication()  # Clears saved token
```

### intent_parser.py

```python
# Detect email intent
IntentParser.detect_intent(user_input)  # Returns: "send_email" or None

# Extract recipient
IntentParser.extract_recipient(user_input)  # Returns: email or name

# Extract subject context
IntentParser.extract_subject_context(user_input)  # Returns: topic string

# Extract tone
IntentParser.extract_tone(user_input)  # Returns: tone string

# Parse complete email request
IntentParser.parse_email_request(user_input)
# Returns: {recipient, subject_context, tone, raw_input} or None
```

### email_composer.py

```python
composer = EmailComposer(model="deepseek-r1:1.5b")

# Generate email
composer.generate_email(
    recipient="user name",
    subject_context="what about",
    tone="professional",
    additional_context=""  # optional
)  # Returns: {success, subject, body, error}

# Validate email
EmailComposer.validate_email_address("email@domain.com")

# Resolve name to email
EmailComposer.resolve_recipient_name_to_email(
    "Rahul",
    contacts_dict  # optional
)
```

### contacts_manager.py

```python
manager = ContactsManager()

# Add contact
manager.add_contact("Rahul", "rahul@example.com")

# Get contact email
manager.get_contact_email("Rahul")

# Get all contacts
manager.get_all_contacts()  # Returns: dict

# Search contacts
manager.search_contacts("rahul")

# Remove contact
manager.remove_contact("Rahul")

# Check if exists
manager.contact_exists("Rahul")
```

---

## 🚀 Future Enhancements

- [ ] Email templates library
- [ ] Scheduled email sending
- [ ] Email tracking
- [ ] Multiple account support
- [ ] Email scheduling with natural language
- [ ] Email reply with AI
- [ ] Attachment support
- [ ] Email analytics
- [ ] Team collaboration features

---

## 📞 Support

For issues or questions:

1. Check the troubleshooting section
2. Review error logs
3. Verify all dependencies are installed
4. Ensure Ollama and Gmail API are properly configured

---

**Status**: ✅ Production Ready (Testing Phase)

Last Updated: May 8, 2026
