async function submitText() {
    const textInput = document.getElementById('textInput');
    const textOutput = document.getElementById('textOutput');
    const loading = document.getElementById('loading');
    const submitBtn = document.getElementById('submitBtn');
    
    const inputText = textInput.value.trim();
    
    if (!inputText) {
        textOutput.textContent = 'Please enter some text first!';
        textOutput.style.color = '#dc3545';
        return;
    }
    
    // Show loading state
    loading.style.display = 'block';
    submitBtn.disabled = true;
    textOutput.textContent = '';
    
    try {
        const response = await fetch('/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text: inputText })
        });
        
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        
        const data = await response.json();
        textOutput.textContent = data.output;
        textOutput.style.color = '#333';
        
    } catch (error) {
        console.error('Error:', error);
        textOutput.textContent = 'Error processing your request. Please try again.';
        textOutput.style.color = '#dc3545';
    } finally {
        // Hide loading state
        loading.style.display = 'none';
        submitBtn.disabled = false;
    }
}

// Allow Enter key to submit (Ctrl+Enter for new line)
document.getElementById('textInput').addEventListener('keydown', function(event) {
    if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey) {
        event.preventDefault();
        submitText();
    }
});