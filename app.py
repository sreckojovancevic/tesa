from flask import Flask, request, render_template, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import uuid
import redis
from rq import Queue
from tasks import process_ocr  # Import the OCR processing function

app = Flask(__name__)

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Configure Redis
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

# Set up RQ
redis_conn = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
queue = Queue(connection=redis_conn)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.after_request
def add_cache_control(response):
    # Add Cache-Control headers to all responses
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'  # Prevent caching
    response.headers['Pragma'] = 'no-cache'  # For HTTP 1.0 compatibility
    response.headers['Expires'] = '0'  # For proxies
    return response

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('index.html', error='No file part')

        file = request.files['file']
        if file.filename == '':
            return render_template('index.html', error='No selected file')

        if file and allowed_file(file.filename):
            language = request.form.get('language', 'eng')
            filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4()) + "_" + filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            # Check if result is in cache
            file_key = filename + "_" + language
            cached_result = redis_client.get(file_key)
            if cached_result:
                return render_template('index.html', text=cached_result)
            else:
                job = queue.enqueue(process_ocr, file_path, language, job_timeout=6000)  # Set timeout to 10 minutes
                print(f"Enqueued job with ID: {job.id}")
                return render_template('index.html', job_id=job.id)
        else:
            return render_template('index.html', error='Invalid file type')
    
    return render_template('index.html')

@app.route('/job/<job_id>')
def check_job(job_id):
    job = queue.fetch_job(job_id)
    if job is None:
        return jsonify({"error": "Job not found"}), 404
    
    if job.is_finished:
        result, docx_path = job.result
        response = jsonify({"result": result, "docx_path": docx_path})
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'  # Prevent caching
        response.headers['Pragma'] = 'no-cache'  # For HTTP 1.0 compatibility
        response.headers['Expires'] = '0'  # For proxies
        return response
    elif job.is_failed:
        return jsonify({"status": "failed"}), 500
    else:
        return jsonify({"status": "processing"}), 202

@app.route('/download/<path:filename>', methods=['GET'])
def download_file(filename):
    response = send_file(filename, as_attachment=True)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'  # Prevent caching
    response.headers['Pragma'] = 'no-cache'  # For HTTP 1.0 compatibility
    response.headers['Expires'] = '0'  # For proxies
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
