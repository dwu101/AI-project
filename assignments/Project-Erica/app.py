from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

# Your Google Colab ngrok URL (update this with your actual URL)
COLAB_URL = "https://undaggled-nonrustically-eusebio.ngrok-free.dev"

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_text():
    """Process the text input through Ollama on Google Colab"""
    data = request.get_json()
    user_input = data.get('text', '')
    
    if not user_input:
        return jsonify({'output': 'Please enter some text'}), 400
    
    try:
        # Send request to Google Colab endpoint
        response = requests.post(
            f"{COLAB_URL}/query",
            json={'query': user_input},
            timeout=120  # 2 minute timeout for longer responses
        )
        
        # Check if request was successful
        response.raise_for_status()
        
        # Get the response from Colab
        colab_response = response.json()
        
        if colab_response.get('status') == 'success':
            processed_output = colab_response.get('response', 'No response received')
        else:
            processed_output = f"Error: {colab_response.get('error', 'Unknown error')}"
            
    except requests.exceptions.Timeout:
        processed_output = "Request timed out. The model might be taking too long to respond."
    except requests.exceptions.RequestException as e:
        processed_output = f"Error connecting to Colab: {str(e)}\n\nMake sure your Colab notebook is running and the ngrok URL is correct."
    except Exception as e:
        processed_output = f"Unexpected error: {str(e)}"
    
    return jsonify({'output': processed_output})

@app.route('/health', methods=['GET'])
def health():
    """Check if Colab endpoint is reachable"""
    try:
        response = requests.get(f"{COLAB_URL}/health", timeout=10)
        return jsonify({
            'local': 'healthy',
            'colab': response.json()
        })
    except Exception as e:
        return jsonify({
            'local': 'healthy',
            'colab': f'unreachable: {str(e)}'
        }), 503

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)  # Changed to 5001 to avoid conflict