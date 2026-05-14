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

# Slack workflows
from slack.send_message_workflow import render_send_message_workflow
from slack.channels_workflow import render_channels_workflow
from slack.search_workflow import render_search_workflow as render_slack_search_workflow
from slack.delete_workflow import render_delete_workflow as render_slack_delete_workflow
from slack.settings_workflow import render_settings_workflow as render_slack_settings_workflow

# Notion workflows
from notion.notion_workflow import render_notion_workflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

st.set_page_config(
    page_title="DeepSeek AI Assistant",
    page_icon="🧠",
    layout="wide",
)

# Global OAuth Callback Handler for Notion
if "code" in st.query_params:
    st.session_state.current_view = "notion"

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

    .stChatMessage {
        background: transparent !important;
    }

    [data-testid="stChatMessageContent"] {
        border-radius: 12px;
    }

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

    .stSelectbox div[data-baseweb="select"],
    .stSelectbox div[data-baseweb="select"] svg,
    .stSelectbox [role="combobox"],
    div[data-baseweb="select"] svg[title="open"],
    div[data-baseweb="select"] svg[title="close"] {
        cursor: pointer !important;
    }

    .stSpinner > div { border-top-color: #6c63ff !important; }

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

    div[data-testid="column"] {
        width: fit-content !important;
        flex: unset !important;
        min-width: unset !important;
    }

    .nav-btn button {
        width: 150px !important;
        height: 45px !important;
        padding: 8px 12px !important;
        border: 1px solid rgba(108, 99, 255, 0.4) !important;
        background: #1a1a1a !important;
        color: #e8e8e8 !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        transition: all 0.3s ease !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    .nav-btn button:hover {
        border-color: #6c63ff !important;
        background: rgba(108, 99, 255, 0.1) !important;
        transform: translateY(-2px);
    }
</style>
""", unsafe_allow_html=True)

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
        key="selected_model",
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

    if st.button("🗑️ Clear Chat", key="clear_chat_sidebar", use_container_width=True):
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


if "message_log" not in st.session_state:
    st.session_state.message_log = [
        {"role": "ai", "content": _welcome_message()}
    ]

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


st.markdown('<div class="page-title">🧠 DeepSeek AI Assistant</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-subtitle">Local AI chatbot powered by DeepSeek via Ollama</div>',
    unsafe_allow_html=True,
)

if "email_history" not in st.session_state:
    st.session_state.email_history = []
if "draft_history" not in st.session_state:
    st.session_state.draft_history = []
if "contacts_manager" not in st.session_state:
    st.session_state.contacts_manager = ContactsManager()
if "email_composer" not in st.session_state:
    st.session_state.email_composer = EmailComposer(model=selected_model)
if "current_view" not in st.session_state:
    st.session_state.current_view = "chat"

st.markdown("### ⚙️ Tools")
col_nav1, col_nav2, col_nav3, col_nav4, col_spacer = st.columns([0.12, 0.12, 0.12, 0.12, 0.52], gap="small")

with col_nav1:
    st.markdown('<div class="nav-btn">', unsafe_allow_html=True)
    if st.button("💬 AI Chat", key="nav_chat_btn"):
        st.session_state.current_view = "chat"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with col_nav2:
    st.markdown('<div class="nav-btn">', unsafe_allow_html=True)
    if st.button("📧 Gmail", key="nav_email_btn"):
        st.session_state.current_view = "email"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with col_nav3:
    st.markdown('<div class="nav-btn">', unsafe_allow_html=True)
    if st.button("💬 Slack", key="nav_slack_btn"):
        st.session_state.current_view = "slack"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with col_nav4:
    st.markdown('<div class="nav-btn">', unsafe_allow_html=True)
    if st.button("📝 Notion", key="nav_notion_btn"):
        st.session_state.current_view = "notion"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.current_view == "chat":
    st.divider()
    for message in st.session_state.message_log:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

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

elif st.session_state.current_view == "email":
    st.divider()
    tab_send, tab_inbox, tab_search, tab_delete, tab_settings = st.tabs([
        "📧 Send Email", "📥 Listing", "🔍 Search", "🗑️ Delete", "⚙️ Settings"
    ])

    with tab_send:
        render_send_email_workflow()

    with tab_inbox:
        render_inbox_workflow()

    with tab_search:
        render_search_workflow()

    with tab_delete:
        render_delete_workflow()

    with tab_settings:
        st.header("⚙️ Settings")
        st.subheader("🔐 Gmail Authentication")
        if is_gmail_authenticated():
            auth_email = get_authenticated_email()
            st.success(f"✅ Authenticated as: {auth_email}")
            if st.button("🔓 Disconnect Gmail", key="disconnect_gmail", use_container_width=True):
                if clear_authentication():
                    st.success("✅ Gmail disconnected")
                    st.rerun()
        else:
            st.info("Gmail authentication is required to send emails.")
            if st.button("🔓 Authenticate with Gmail", key="auth_gmail", use_container_width=True):
                try:
                    with st.spinner("Opening Gmail authentication..."):
                        authenticate_gmail()
                        st.success("✅ Gmail authenticated successfully!")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

        st.divider()
        st.subheader("📇 Contacts Management")
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Add New Contact**")
            n_name = st.text_input("Contact name", key="add_contact_name")
            n_email = st.text_input("Email address", key="add_contact_email")
            if st.button("➕ Add Contact", key="add_contact_btn", use_container_width=True):
                if n_name and n_email:
                    if st.session_state.contacts_manager.add_contact(n_name, n_email):
                        st.success(f"✅ Added: {n_name}")
                        st.rerun()
        with c2:
            st.write("**Saved Contacts**")
            contacts = st.session_state.contacts_manager.get_all_contacts()
            if contacts:
                for name, email in contacts.items():
                    col_n, col_d = st.columns([3, 1])
                    with col_n:
                        st.write(f"**{name}:** {email}")
                    with col_d:
                        if st.button("🗑️", key=f"del_{name}"):
                            st.session_state.contacts_manager.remove_contact(name)
                            st.rerun()

elif st.session_state.current_view == "slack":
    st.divider()
    tab_slack_send, tab_slack_listing, tab_slack_search, tab_slack_delete, tab_slack_settings = st.tabs([
        "📨 Send Message", "📋 Listing", "🔍 Search", "🗑️ Delete", "⚙️ Settings"
    ])

    with tab_slack_send:
        render_send_message_workflow()

    with tab_slack_listing:
        render_channels_workflow()

    with tab_slack_search:
        render_slack_search_workflow()

    with tab_slack_delete:
        render_slack_delete_workflow()

    with tab_slack_settings:
        render_slack_settings_workflow()

elif st.session_state.current_view == "notion":
    st.divider()
    render_notion_workflow()

st.markdown("""
<style>
div[data-testid="InputInstructions"] {
    position: absolute !important;
    bottom: -30px !important;
    right: 0 !important;
    font-size: 12px !important;
    background: transparent !important;
    color: #888 !important;
    padding: 0 !important;
}
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
        if (wrapper.querySelector('.st-custom-icons') || !wrapper.querySelector('input[type="text"]')) return;
        const iconContainer = parentDoc.createElement('div');
        iconContainer.className = 'st-custom-icons';
        iconContainer.style.display = 'flex';
        iconContainer.style.gap = '8px';
        iconContainer.style.paddingRight = '12px';
        iconContainer.style.alignItems = 'center';
        iconContainer.style.color = '#888';
        const copyBtn = parentDoc.createElement('span');
        copyBtn.innerHTML = '&#128203;';
        copyBtn.style.cursor = 'pointer';
        copyBtn.style.fontSize = '14px';
        copyBtn.onclick = function(e) {
            e.preventDefault(); e.stopPropagation();
            const input = wrapper.querySelector('input');
            if (input && input.value) {
                parentDoc.defaultView.navigator.clipboard.writeText(input.value);
                copyBtn.innerHTML = '&#10004;';
                setTimeout(() => copyBtn.innerHTML = '&#128203;', 1000);
            }
        };
        const clearBtn = parentDoc.createElement('span');
        clearBtn.innerHTML = '&#10006;';
        clearBtn.style.cursor = 'pointer';
        clearBtn.style.fontSize = '14px';
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
const observer = new MutationObserver((mutations) => { addInputIcons(); });
observer.observe(parentDoc.body, { childList: true, subtree: true });
addInputIcons();
</script>
""", height=0, width=0)