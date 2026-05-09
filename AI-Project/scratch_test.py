import streamlit as st
import streamlit.components.v1 as components

st.text_input("Test input 1")
st.text_input("Test input 2")

components.html("""
<script>
const parentDoc = window.parent.document;
function addIcons() {
    const textInputs = parentDoc.querySelectorAll('div[data-baseweb="input"]');
    textInputs.forEach(wrapper => {
        if (wrapper.querySelector('.st-custom-icons')) return;
        
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
            e.preventDefault();
            e.stopPropagation();
            const input = wrapper.querySelector('input');
            if (input && input.value) {
                parentDoc.defaultView.navigator.clipboard.writeText(input.value);
                copyBtn.innerHTML = '&#10004;';
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
            e.preventDefault();
            e.stopPropagation();
            const input = wrapper.querySelector('input');
            if (input) {
                let nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                nativeInputValueSetter.call(input, '');
                let ev2 = new Event('input', { bubbles: true});
                input.dispatchEvent(ev2);
                let ev3 = new Event('change', { bubbles: true});
                input.dispatchEvent(ev3);
                input.focus();
            }
        };
        
        iconContainer.appendChild(copyBtn);
        iconContainer.appendChild(clearBtn);
        wrapper.appendChild(iconContainer);
        
        // ensure parent doesn't hide it
        wrapper.style.paddingRight = '0px'; 
    });
}

const observer = new MutationObserver((mutations) => {
    addIcons();
});

observer.observe(parentDoc.body, { childList: true, subtree: true });
addIcons();
</script>
""", height=0, width=0)
