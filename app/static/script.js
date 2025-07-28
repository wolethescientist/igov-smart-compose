document.addEventListener('DOMContentLoaded', () => {
    const editor = document.getElementById('editor');
    const suggestionDisplay = document.getElementById('suggestion');
    let currentSuggestion = '';
    let typingTimer;
    const doneTypingInterval = 500;
    
    // Generate a random user ID if not exists
    let userId = localStorage.getItem('user_id');
    if (!userId) {
        userId = 'user_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('user_id', userId);
    }

    function showLoading() {
        suggestionDisplay.innerHTML = 
            '<div class="loading-dots">' +
            '<span></span>' +
            '<span></span>' +
            '<span></span>' +
            '</div>';
    }

    async function getSuggestion() {
        const text = editor.value;
        if (!text.trim()) {
            suggestionDisplay.textContent = '';
            return;
        }

        showLoading();

        try {
            const response = await fetch('/api/generate-suggestion', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    current_text: text,
                    user_id: userId
                })
            });

            if (!response.ok) {
                throw new Error(`API response error: ${response.status}`);
            }

            const data = await response.json();
            currentSuggestion = data.suggestion || '';
            if (currentSuggestion) {
                suggestionDisplay.textContent = currentSuggestion;
            } else {
                suggestionDisplay.textContent = '';
            }
        } catch (error) {
            console.error('Error:', error);
            suggestionDisplay.textContent = '';
        }
    }

    async function sendFeedback(context, selectedSuggestion) {
        try {
            const response = await fetch('/api/feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: userId,
                    context: context,
                    selected_suggestion: selectedSuggestion
                })
            });

            if (!response.ok) {
                throw new Error('Failed to send feedback');
            }
        } catch (error) {
            console.error('Error sending feedback:', error);
        }
    }

    editor.addEventListener('input', () => {
        clearTimeout(typingTimer);
        // Don't clear the suggestion display here, let it keep showing loading
        currentSuggestion = '';
        showLoading(); // Show loading immediately when typing
        typingTimer = setTimeout(getSuggestion, doneTypingInterval);
    });

    editor.addEventListener('keydown', (e) => {
        if (e.key === 'Tab' && currentSuggestion) {
            e.preventDefault();
            const text = editor.value;
            
            // Store the context and suggestion for feedback
            const context = text;
            const selectedSuggestion = currentSuggestion;
            
            // Apply the suggestion
            editor.value = text + currentSuggestion;
            editor.selectionEnd = editor.value.length;
            
            // Clear the current suggestion
            currentSuggestion = '';
            suggestionDisplay.textContent = '';
            
            // Send feedback
            sendFeedback(context, selectedSuggestion);
        }
    });
}); 