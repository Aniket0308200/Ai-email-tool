"""
AI Chatbot with Email Integration
Streamlit UI — DeepSeek + LangChain + Ollama + Gmail API
"""
import logging
import streamlit as st
import streamlit.components.v1 as components
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import (
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
    ChatPromptTemplate,
)

# Import email modules
from email_send.gmail_handler import (
    authenticate_gmail,
    is_gmail_authenticated,
    get_authenticated_email,
    clear_authentication,
)
from email_send.intent_parser import IntentParser
from email_send.email_composer import EmailComposer
from email_send.contacts_manager import ContactsManager
import json
from email_send.send_email_workflow import render_send_email_workflow
from email_send.inbox_workflow import render_inbox_workflow
from email_send.search_workflow import render_search_workflow
from email_send.delete_workflow import render_delete_workflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DeepSeek AI Assistant",
    page_icon="🧠",
    layout="wide",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .main {
        background-color: #0f0f0f;
        color: #e8e8e8;
    }

    section[data-testid="stSidebar"] {
        background-color: #1a1a1a;
        border-right: 1px solid #2a2a2a;
    }

    /* Chat messages */
    .stChatMessage {
        background: transparent !important;
    }

    /* User message bubble */
    [data-testid="stChatMessageContent"] {
        border-radius: 12px;
    }

    /* Input box */
    .stChatInput textarea {
        background-color: #1e1e1e !important;
        color: #e8e8e8 !important;
        border: 1px solid #333 !important;
        border-radius: 12px !important;
    }
    .stChatInput textarea:focus {
        border-color: #6c63ff !important;
        box-shadow: 0 0 0 2px rgba(108, 99, 255, 0.2) !important;
    }

    /* Selectbox */
    .stSelectbox div[data-baseweb="select"] {
        color: #e8e8e8 !important;
        background-color: #1e1e1e !important;
        border-color: #333 !important;
        border-radius: 8px !important;
    }
    .stSelectbox svg { fill: #e8e8e8 !important; }
    div[role="listbox"] div {
        background-color: #1e1e1e !important;
        color: #e8e8e8 !important;
    }

    /* Selectbox & dropdown clickable areas — pointer cursor */
    .stSelectbox div[data-baseweb="select"],
    .stSelectbox div[data-baseweb="select"] svg,
    .stSelectbox [role="combobox"],
    div[data-baseweb="select"] svg[title="open"],
    div[data-baseweb="select"] svg[title="close"] {
        cursor: pointer !important;
    }

    /* Spinner */
    .stSpinner > div { border-top-color: #6c63ff !important; }

    /* Sidebar header */
    .sidebar-brand {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 0 16px;
    }
    .sidebar-brand-icon {
        font-size: 28px;
        line-height: 1;
    }
    .sidebar-brand-text {
        font-size: 18px;
        font-weight: 700;
        background: linear-gradient(135deg, #6c63ff, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* Capability pills */
    .cap-pill {
        display: inline-block;
        background: linear-gradient(135deg, rgba(108,99,255,0.15), rgba(167,139,250,0.1));
        border: 1px solid rgba(108,99,255,0.3);
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 12px;
        color: #a78bfa;
        margin: 3px 2px;
    }

    /* Page title */
    .page-title {
        font-size: 26px;
        font-weight: 700;
        background: linear-gradient(135deg, #6c63ff, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2px;
    }
    .page-subtitle {
        font-size: 13px;
        color: #555;
        margin-bottom: 20px;
    }

    /* Clear button */
    .stButton > button {
        background: linear-gradient(135deg, #6c63ff, #8b5cf6) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: opacity 0.2s ease !important;
    }
    .stButton > button:hover {
        opacity: 0.85 !important;
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">
        <span class="sidebar-brand-icon">🧠</span>
        <span class="sidebar-brand-text">DeepSeek AI</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**⚙️ Configuration**")
    selected_model = st.selectbox(
        "Model",
        ["deepseek-r1:1.5b", "deepseek-r1:3b"],
        index=0,
        label_visibility="collapsed",
    )

    st.divider()

    st.markdown("**💡 Capabilities**")
    capabilities = [
        "🐍 Python Expert",
        "🐞 Debug & Fix",
        "📝 Documentation",
        "💡 Solution Design",
        "🔁 Code Review",
        "⚡ Optimization",
    ]
    pills_html = "".join(f'<span class="cap-pill">{c}</span>' for c in capabilities)
    st.markdown(pills_html, unsafe_allow_html=True)

    st.divider()

    st.markdown("**💬 Example prompts**")
    examples = [
        "*Write a Python function to sort a list*",
        "*Explain async/await in Python*",
        "*Debug this code: ...*",
        "*Review my function for best practices*",
    ]
    for ex in examples:
        st.markdown(f"- {ex}")

    st.divider()

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.message_log = [
            {"role": "ai", "content": _welcome_message()}
        ]
        st.rerun()

    st.markdown(
        "<div style='text-align:center;font-size:11px;color:#444;margin-top:12px'>"
        "Powered by <a href='https://ollama.ai/' style='color:#6c63ff'>Ollama</a> · "
        "<a href='https://python.langchain.com/' style='color:#6c63ff'>LangChain</a>"
        "</div>",
        unsafe_allow_html=True,
    )


# ── Welcome message helper ─────────────────────────────────────────────────────
def _welcome_message() -> str:
    return (
        "👋 Hi! I'm your **DeepSeek AI assistant** — powered by Ollama running locally.\n\n"
        "I can help you with:\n"
        "- 🐍 **Python** code, debugging, and best practices\n"
        "- 💡 **Solution design** and architecture\n"
        "- 📝 **Documentation** and code review\n"
        "- ⚡ **Optimization** and performance\n\n"
        "What would you like to work on today?"
    )


# ── Session state ──────────────────────────────────────────────────────────────
if "message_log" not in st.session_state:
    st.session_state.message_log = [
        {"role": "ai", "content": _welcome_message()}
    ]

# ── LLM setup ─────────────────────────────────────────────────────────────────
llm_engine = ChatOllama(
    model=selected_model,
    base_url="http://localhost:11434",
    temperature=0.3,
)

system_prompt = SystemMessagePromptTemplate.from_template(
    "You are an expert AI coding assistant. Provide concise, correct solutions "
    "with clear explanations. Use code blocks for all code samples. "
    "Always respond in English."
)


def build_prompt_chain():
    seq = [system_prompt]
    for msg in st.session_state.message_log:
        if msg["role"] == "user":
            seq.append(HumanMessagePromptTemplate.from_template(msg["content"]))
        elif msg["role"] == "ai":
            seq.append(AIMessagePromptTemplate.from_template(msg["content"]))
    return ChatPromptTemplate.from_messages(seq)


def generate_response(prompt_chain) -> str:
    return (prompt_chain | llm_engine | StrOutputParser()).invoke({})


# ── Page title ─────────────────────────────────────────────────────────────────
st.markdown('<div class="page-title">🧠 DeepSeek AI Assistant</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-subtitle">Local AI chatbot powered by DeepSeek via Ollama</div>',
    unsafe_allow_html=True,
)

# ── Initialize session state for email ─────────────────────────────────────────
if "email_history" not in st.session_state:
    st.session_state.email_history = []
if "draft_history" not in st.session_state:
    st.session_state.draft_history = []
if "contacts_manager" not in st.session_state:
    st.session_state.contacts_manager = ContactsManager()
if "email_composer" not in st.session_state:
    st.session_state.email_composer = EmailComposer(model=selected_model)

# ── Tabs for Chat and Email ────────────────────────────────────────────────────
tab_chat, tab_email, tab_inbox, tab_search, tab_delete, tab_settings = st.tabs([
    "💬 Chat", "📧 Send Email", "📥 Listing", "🔍 Search", "🗑️ Delete", "⚙️ Settings"
])

# ────────────────────────────────────────────────────────────────────────────────
# CHAT TAB
# ────────────────────────────────────────────────────────────────────────────────
with tab_chat:
    # ── Chat display ───────────────────────────────────────────────────────────
    for message in st.session_state.message_log:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # ── Chat input ─────────────────────────────────────────────────────────────
    user_query = st.chat_input("Ask me anything about coding…")

    if user_query:
        st.session_state.message_log.append({"role": "user", "content": user_query})

        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("ai"):
            with st.spinner("🧠 Thinking…"):
                prompt_chain = build_prompt_chain()
                ai_response = generate_response(prompt_chain)
            st.markdown(ai_response)

        st.session_state.message_log.append({"role": "ai", "content": ai_response})
        st.rerun()

# ────────────────────────────────────────────────────────────────────────────────
# EMAIL TAB
# ────────────────────────────────────────────────────────────────────────────────
with tab_email:
    render_send_email_workflow()

# ────────────────────────────────────────────────────────────────────────────────
# INBOX TAB
# ────────────────────────────────────────────────────────────────────────────────
with tab_inbox:
    render_inbox_workflow()

# ────────────────────────────────────────────────────────────────────────────────
# SEARCH TAB
# ────────────────────────────────────────────────────────────────────────────────
with tab_search:
    render_search_workflow()

# ────────────────────────────────────────────────────────────────────────────────
# DELETE TAB
# ────────────────────────────────────────────────────────────────────────────────
with tab_delete:
    render_delete_workflow()

# ────────────────────────────────────────────────────────────────────────────────
# SETTINGS TAB
# ────────────────────────────────────────────────────────────────────────────────
with tab_settings:
    st.header("⚙️ Settings")
    
    # Gmail Authentication
    st.subheader("🔐 Gmail Authentication")
    
    if is_gmail_authenticated():
        auth_email = get_authenticated_email()
        st.success(f"✅ Authenticated as: {auth_email}")
        
        if st.button("🔓 Disconnect Gmail", use_container_width=True):
            if clear_authentication():
                st.success("✅ Gmail disconnected")
                st.rerun()
    else:
        st.info("Gmail authentication is required to send emails.")
        if st.button("🔓 Authenticate with Gmail", use_container_width=True):
            try:
                with st.spinner("Opening Gmail authentication..."):
                    authenticate_gmail()
                    st.success("✅ Gmail authenticated successfully!")
                    st.rerun()
            except FileNotFoundError as e:
                st.error(f"❌ {str(e)}")
                st.info(
                    "To set up Gmail authentication:\n"
                    "1. Go to https://console.cloud.google.com/\n"
                    "2. Create a new project\n"
                    "3. Enable Gmail API\n"
                    "4. Create OAuth 2.0 Desktop credentials\n"
                    "5. Download credentials.json\n"
                    "6. Place it in: `email_send/email_credentials/credentials.json`"
                )
            except ValueError as e:
                st.error(f"Authentication setup issue: {str(e)}")
                st.info(
                    "Fastest fix:\n"
                    "1. Open Google Cloud Console > APIs & Services > Credentials\n"
                    "2. Create OAuth client ID with Application type: Desktop app\n"
                    "3. Download the JSON file\n"
                    "4. Put it in `AI-Project/email_send/email_credentials/credentials.json`\n\n"
                    "If you keep using a Web OAuth client, add this exact Authorized redirect URI:\n"
                    "`http://localhost:8080/`"
                )
            except Exception as e:
                st.error(f"❌ Authentication failed: {str(e)}")
    
    st.divider()
    
    # Contacts Management
    st.subheader("📇 Contacts Management")
    
    contact_tab1, contact_tab2 = st.columns(2)
    
    with contact_tab1:
        st.write("**Add New Contact**")
        new_contact_name = st.text_input("Contact name")
        new_contact_email = st.text_input("Email address")
        
        if st.button("➕ Add Contact", use_container_width=True):
            if new_contact_name and new_contact_email:
                if st.session_state.contacts_manager.add_contact(
                    new_contact_name, new_contact_email
                ):
                    st.success(f"✅ Added: {new_contact_name}")
                    st.rerun()
            else:
                st.error("❌ Please fill in all fields")
    
    with contact_tab2:
        st.write("**Saved Contacts**")
        contacts = st.session_state.contacts_manager.get_all_contacts()
        
        if contacts:
            for name, email in contacts.items():
                col_name, col_delete = st.columns([3, 1])
                with col_name:
                    st.write(f"**{name}:** {email}")
                with col_delete:
                    if st.button("🗑️", key=f"delete_{name}"):
                        st.session_state.contacts_manager.remove_contact(name)
                        st.rerun()
        else:
            st.info("No contacts saved yet")
    
    with st.expander("🛠️ Advanced Settings", expanded=False):
        st.info("Advanced configuration options will go here.")



    
    st.divider()
    
    # LLM Model Configuration
    st.subheader("🤖 AI Model Settings")
    
    current_model = selected_model
    st.info(f"Currently using: **{current_model}**")
    st.write("Available models: deepseek-r1:1.5b, deepseek-r1:3b")
    st.write("(Change model in main Configuration section)")
    
    st.divider()
    
    # Application Info
    st.subheader("ℹ️ Application Info")
    st.write("""
    **DeepSeek AI Assistant with Email Integration**
    
    - **Chat:** Local AI-powered coding assistant
    - **Email:** Direct email sending via Gmail API
    - **Contacts:** Save and manage email contacts
    - **LLM:** DeepSeek via Ollama
    
    Built with: Streamlit, LangChain, Gmail API, Ollama
    """)

# ────────────────────────────────────────────────────────────────────────────────
# GLOBAL UI ENHANCEMENTS (CSS & JS for Text Inputs)
# ────────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Move 'Press Enter to apply' below the input box so it doesn't overlap our icons */
div[data-testid="InputInstructions"] {
    position: absolute !important;
    bottom: -30px !important;
    right: 0 !important;
    font-size: 12px !important;
    background: transparent !important;
    color: #888 !important;
    padding: 0 !important;
}
/* Ensure the parent container has enough space at the bottom */
div[data-testid="stTextInput"] > div {
    margin-bottom: 8px; 
}
</style>
""", unsafe_allow_html=True)

components.html("""
<script>
const parentDoc = window.parent.document;
function addInputIcons() {
    const textInputs = parentDoc.querySelectorAll('div[data-baseweb="input"]');
    textInputs.forEach(wrapper => {
        // Skip if icons already added or if it's not a text input
        if (wrapper.querySelector('.st-custom-icons') || !wrapper.querySelector('input[type="text"]')) return;
        
        const iconContainer = parentDoc.createElement('div');
        iconContainer.className = 'st-custom-icons';
        iconContainer.style.display = 'flex';
        iconContainer.style.gap = '8px';
        iconContainer.style.paddingRight = '12px';
        iconContainer.style.alignItems = 'center';
        iconContainer.style.color = '#888';
        
        // Copy icon
        const copyBtn = parentDoc.createElement('span');
        copyBtn.innerHTML = '&#128203;'; // clipboard
        copyBtn.style.cursor = 'pointer';
        copyBtn.style.fontSize = '14px';
        copyBtn.title = 'Copy text';
        copyBtn.onclick = function(e) {
            e.preventDefault(); e.stopPropagation();
            const input = wrapper.querySelector('input');
            if (input && input.value) {
                parentDoc.defaultView.navigator.clipboard.writeText(input.value);
                copyBtn.innerHTML = '&#10004;'; // checkmark
                setTimeout(() => copyBtn.innerHTML = '&#128203;', 1000);
            }
        };
        
        // Clear icon
        const clearBtn = parentDoc.createElement('span');
        clearBtn.innerHTML = '&#10006;'; // cross
        clearBtn.style.cursor = 'pointer';
        clearBtn.style.fontSize = '14px';
        clearBtn.title = 'Clear text';
        clearBtn.onclick = function(e) {
            e.preventDefault(); e.stopPropagation();
            const input = wrapper.querySelector('input');
            if (input) {
                let nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                nativeInputValueSetter.call(input, '');
                input.dispatchEvent(new Event('input', { bubbles: true}));
                input.dispatchEvent(new Event('change', { bubbles: true}));
                input.focus();
            }
        };
        
        iconContainer.appendChild(copyBtn);
        iconContainer.appendChild(clearBtn);
        wrapper.appendChild(iconContainer);
        wrapper.style.paddingRight = '0px'; 
    });
}

// Observe DOM for new inputs (Streamlit reruns)
const observer = new MutationObserver((mutations) => { addInputIcons(); });
observer.observe(parentDoc.body, { childList: true, subtree: true });
addInputIcons();
</script>
""", height=0, width=0)
