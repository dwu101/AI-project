from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_text():
    """Process the text input and return a response"""
    data = request.get_json()
    user_input = data.get('text', '')

    processed_output = f"You entered: {user_input}\nReversed: {user_input[::-1]}"
    
    return jsonify({'output': processed_output})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)