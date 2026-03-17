from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import os
from ingestion.ingest_pdf import ingest_pdf
from agent.planner import agent_query
from openai import OpenAI

# Initialize the OpenAI client
llm_client = OpenAI(
    api_key="api key",
    base_url="url"
)

def ask_llm(context, question):
    prompt = f"""
Use the following context to answer the question.

Context:
{context}

Question:
{question}
"""
    response = llm_client.chat.completions.create(
        model="meta-llama/llama-3-8b-instruct",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

app = Flask(__name__, static_folder='../project ui')

# Configuration
UPLOAD_FOLDER = 'data'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return send_from_directory('../project ui', 'index.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        try:
            ingest_pdf(file_path)
            return jsonify({"message": f"File {filename} uploaded and ingested successfully"}), 200
        except Exception as e:
            return jsonify({"error": f"Failed to ingest file: {str(e)}"}), 500

@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    question = data.get('question')
    if not question:
        return jsonify({"error": "Question is required"}), 400
    try:
        context = agent_query(question)
        answer = ask_llm(context, question)
        return jsonify({"answer": answer, "context": context})
    except Exception as e:
        return jsonify({"error": f"Failed to get answer: {str(e)}"}), 500

if __name__ == '__main__':
    # Ensure the upload folder exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True, port=8000)
