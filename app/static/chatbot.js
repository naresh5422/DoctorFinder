(function () {
    const widget = document.querySelector('.care-chatbot');
    if (!widget) return;

    const panel = widget.querySelector('.care-chatbot-panel');
    const toggle = widget.querySelector('.care-chatbot-toggle');
    const closeButton = widget.querySelector('.care-chatbot-close');
    const messages = widget.querySelector('.care-chatbot-messages');
    const form = widget.querySelector('.care-chatbot-form');
    const input = form.querySelector('input[name="message"]');
    const voiceButton = widget.querySelector('.care-chatbot-voice');
    const faqs = widget.querySelector('.care-chatbot-toolbar');
    const endpoint = widget.dataset.chatbotEndpoint;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;

    function setOpen(isOpen) {
        panel.hidden = !isOpen;
        toggle.setAttribute('aria-expanded', String(isOpen));
        sessionStorage.setItem('careChatbotOpen', isOpen ? '1' : '0');
        if (isOpen) input.focus();
    }

    function scrollToLatest() {
        messages.scrollTop = messages.scrollHeight;
    }

    function addMessage(text, sender, actions) {
        const row = document.createElement('div');
        row.className = `care-chatbot-message ${sender}`;

        const bubble = document.createElement('div');
        bubble.className = 'care-chatbot-bubble';
        bubble.textContent = text;
        row.appendChild(bubble);

        if (actions && actions.length) {
            const actionWrap = document.createElement('div');
            actionWrap.className = 'care-chatbot-actions';
            actions.forEach((action) => {
                const link = document.createElement('a');
                link.href = action.url;
                link.className = `care-chatbot-action ${action.style || 'primary'}`;
                link.textContent = action.label;
                actionWrap.appendChild(link);
            });
            bubble.appendChild(actionWrap);
        }

        messages.appendChild(row);
        scrollToLatest();
        return row;
    }

    function addTypingIndicator() {
        const row = document.createElement('div');
        row.className = 'care-chatbot-message bot typing';

        const bubble = document.createElement('div');
        bubble.className = 'care-chatbot-bubble care-chatbot-typing';
        bubble.innerHTML = '<span></span><span></span><span></span>';
        row.appendChild(bubble);

        messages.appendChild(row);
        scrollToLatest();
        return row;
    }

    function setVoiceState(isListening) {
        voiceButton.classList.toggle('listening', isListening);
        voiceButton.setAttribute('aria-label', isListening ? 'Listening for voice input' : 'Start voice input');
    }

    async function sendMessage(message) {
        const cleanMessage = message.trim();
        if (!cleanMessage) return;

        addMessage(cleanMessage, 'user');
        input.value = '';
        input.disabled = true;

        const typing = addTypingIndicator();

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({message: cleanMessage})
            });
            const data = await response.json();
            typing.remove();
            addMessage(data.reply || 'I could not prepare a response.', 'bot', data.actions || []);
        } catch (error) {
            typing.remove();
            addMessage('Connection problem. Please try again in a moment.', 'bot');
        } finally {
            input.disabled = false;
            input.focus();
        }
    }

    toggle.addEventListener('click', () => setOpen(panel.hidden));
    closeButton.addEventListener('click', () => setOpen(false));
    form.addEventListener('submit', (event) => {
        event.preventDefault();
        sendMessage(input.value);
    });
    faqs.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-message]');
        if (button) sendMessage(button.dataset.message);
    });

    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.lang = 'en-IN';
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.addEventListener('start', () => setVoiceState(true));
        recognition.addEventListener('end', () => setVoiceState(false));
        recognition.addEventListener('result', (event) => {
            const transcript = event.results[0][0].transcript;
            input.value = transcript;
            sendMessage(transcript);
        });
        recognition.addEventListener('error', () => {
            setVoiceState(false);
            addMessage('Voice input is not available right now. You can type your question instead.', 'bot');
        });

        voiceButton.addEventListener('click', () => {
            setOpen(true);
            try {
                recognition.start();
            } catch (error) {
                setVoiceState(false);
            }
        });
    } else {
        voiceButton.disabled = true;
        voiceButton.title = 'Voice input is not supported in this browser';
    }

    setOpen(sessionStorage.getItem('careChatbotOpen') === '1');
})();
