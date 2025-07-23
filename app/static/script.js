document.addEventListener('DOMContentLoaded', () => {
    const editor = document.getElementById('editor');
    const suggestion = document.getElementById('suggestion');
    let typingTimer;
    const doneTypingInterval = 500;
    let currentSuggestion = '';
    let isLoading = false;
    let lastProcessedText = '';

    // Function to safely escape HTML
    function escapeHtml(text) {
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Function to update suggestion display position
    function updateSuggestionPosition() {
        const cursorPosition = editor.selectionStart;
        const text = editor.value;
        
        if (cursorPosition === text.length) {  // Only show suggestion at the end
            const textBeforeCursor = text.substring(0, cursorPosition);
            
            let suggestionContent = '';
            if (isLoading) { 
                suggestionContent = '<span class="suggestion-text loading">...</span>';
            } else if (currentSuggestion) {
                // Check if the suggestion would create a duplicate
                const words = textBeforeCursor.trim().split(/\s+/);
                const lastWord = words[words.length - 1] || '';
                const lastPhrase = words.slice(-3).join(' '); // Get last 3 words
                
                let suggestionToShow = currentSuggestion;
                
                // Check for both single word and phrase duplicates
                if (lastWord && (
                    suggestionToShow.toLowerCase().startsWith(lastWord.toLowerCase()) ||
                    suggestionToShow.toLowerCase().startsWith(lastPhrase.toLowerCase())
                )) {
                    const matchLength = Math.max(
                        lastWord.length,
                        suggestionToShow.toLowerCase().startsWith(lastPhrase.toLowerCase()) ? lastPhrase.length : 0
                    );
                    suggestionToShow = suggestionToShow.substring(matchLength).trimStart();
                }
                
                if (suggestionToShow.trim()) {
                    suggestionContent = `<span class="suggestion-text">${escapeHtml(suggestionToShow)}</span>`;
                }
            }
            
            suggestion.innerHTML = suggestionContent;
        } else {
            suggestion.innerHTML = '';
        }
    }

    // Function to get suggestions from the API
    async function getSuggestion(text) {
        if (!text.trim() || text === lastProcessedText) return;
        
        isLoading = true;
        updateSuggestionPosition();

        try {
            const response = await fetch('/api/generate-suggestion', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    current_text: text
                })
            });

            if (!response.ok) {
                throw new Error(`Network response was not ok: ${response.status}`);
            }

            const data = await response.json();
            currentSuggestion = data.suggestion;
            lastProcessedText = text;
        } catch (error) {
            console.error('Error fetching suggestion:', error);
            currentSuggestion = '';
        } finally {
            isLoading = false;
            updateSuggestionPosition();
        }
    }

    // Handle typing events with debounce
    editor.addEventListener('input', () => {
        clearTimeout(typingTimer);
        
        // Only clear current suggestion if the text has changed
        if (editor.value !== lastProcessedText) {
            currentSuggestion = '';
            updateSuggestionPosition();
            
            if (editor.value) {
                typingTimer = setTimeout(() => {
                    getSuggestion(editor.value);
                }, doneTypingInterval);
            }
        }
    });

    // Handle cursor movement
    editor.addEventListener('keyup', (e) => {
        // Update on arrow keys, home, end, etc.
        if (e.key.startsWith('Arrow') || e.key === 'Home' || e.key === 'End') {
            updateSuggestionPosition();
        }
    });

    // Handle mouse clicks for cursor position
    editor.addEventListener('click', () => {
        updateSuggestionPosition();
    });

    // Add resize observer to handle editor size changes
    const resizeObserver = new ResizeObserver(() => {
        if (currentSuggestion) {
            updateSuggestionPosition();
        }
    });
    resizeObserver.observe(editor);

    // Handle window resize
    window.addEventListener('resize', () => {
        if (currentSuggestion) {
            updateSuggestionPosition();
        }
    });

    // Handle editor scroll
    editor.addEventListener('scroll', () => {
        if (currentSuggestion) {
            updateSuggestionPosition();
        }
    });

    // Handle tab key to accept suggestion
    editor.addEventListener('keydown', (e) => {
        if (e.key === 'Tab' && currentSuggestion) {
            e.preventDefault();
            const cursorPosition = editor.selectionStart;
            const text = editor.value;
            const textBeforeCursor = text.substring(0, cursorPosition);
            const words = textBeforeCursor.trim().split(/\s+/);
            const lastWord = words[words.length - 1] || '';
            const lastPhrase = words.slice(-3).join(' ');
            
            let suggestionToAdd = currentSuggestion;
            if (lastWord && (
                suggestionToAdd.toLowerCase().startsWith(lastWord.toLowerCase()) ||
                suggestionToAdd.toLowerCase().startsWith(lastPhrase.toLowerCase())
            )) {
                const matchLength = Math.max(
                    lastWord.length,
                    suggestionToAdd.toLowerCase().startsWith(lastPhrase.toLowerCase()) ? lastPhrase.length : 0
                );
                suggestionToAdd = suggestionToAdd.substring(matchLength).trimStart();
            }
            
            editor.value = text.substring(0, cursorPosition) + 
                          suggestionToAdd + 
                          text.substring(cursorPosition);
            editor.selectionStart = editor.selectionEnd = cursorPosition + suggestionToAdd.length;
            currentSuggestion = '';
            lastProcessedText = editor.value;
            updateSuggestionPosition();
        }
    });

    // Initial update
    updateSuggestionPosition();
}); 