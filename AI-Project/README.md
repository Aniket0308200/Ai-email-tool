# 🧠 DeepSeek AI Assistant

A simple, local AI chatbot built with **Streamlit**, **LangChain**, and **Ollama** (DeepSeek models).

## Features

- 💬 Conversational AI with full chat history
- 🐍 Expert coding assistance (Python, debugging, design, review)
- ⚡ Runs 100% locally — no internet required after setup
- 🎨 Dark-themed UI with a clean modern design

## Requirements

- Python 3.10+
- [Ollama](https://ollama.ai/) installed and running locally

## Setup

### 1. Install Ollama

Download and install from [https://ollama.ai/](https://ollama.ai/), then pull a model:

```bash
ollama pull deepseek-r1:1.5b
```

### 2. Install Python dependencies

```powershell
pip install -r requirements.txt
```

### 3. Activate the virtual environment (Windows)

```powershell
cd D:\AI-email-test\AI-Project
.\.venv\Scripts\Activate.ps1
```

### 4. Run the app

```powershell
streamlit run app.py
```

If `streamlit` is not found, run:

```powershell
python -m streamlit run app.py
```

### 5. Open in browser

Open this URL in your browser:

```text
http://localhost:8501
```

## Models

| Model              | Size  | Speed      |
| ------------------ | ----- | ---------- |
| `deepseek-r1:1.5b` | ~1 GB | ⚡ Fast    |
| `deepseek-r1:3b`   | ~2 GB | 🧠 Smarter |

Switch between models in the sidebar at any time.

## Project Structure

```
AI-Project/
├── app.py           # Main Streamlit application
├── requirements.txt # Python dependencies
└── README.md        # This file
```
