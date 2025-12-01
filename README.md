# To Run

put LLM_RAG_backend.ipynb into google collab, and execute it with a GPU instance. Ensure to set ngrok_token as a secret environment variable first.

You should see: PUBLIC URL: NgrokTunnel: "(link)" -> "http://localhost:5000"

Then on local machine:
(may need to go into the virtual environement first)

cd into assignments/Project-Erica

pip install -r requirements.txt

python3 app.py

a link should show up in the terminal to open the page on localhost port 5000

**ensure that the link in NgrokTunnel: "(link)" in the google collab output cell is the same as COLAB_URL in app.py