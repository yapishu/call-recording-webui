from flask import Flask, Response, render_template, jsonify, request, send_from_directory, send_file, session, redirect, url_for, abort, flash
from flask_apscheduler import APScheduler
from datetime import datetime
import boto3
from botocore.exceptions import NoCredentialsError
import json
import wsgiserver
import pandas as pd
import gevent
import indexer
import var
import io
import re
from flask import session

app = Flask(__name__)
app.secret_key = var.secret_key
scheduler = APScheduler()

@scheduler.task('interval', id = 'import_cron', hours = 6, misfire_grace_time = 300)
def import_cron():
    crontime = datetime.now().strftime('%H:%M:%S')
    print(f'{crontime} Importing new records')
    gevent.spawn(indexer.importer())

scheduler.init_app(app)
scheduler.start()
scheduler.add_job(func=import_cron, id="import")

@app.route("/stream/<uuid>")
def stream(uuid):
    if 'username' not in session:
        return redirect(url_for('login'))
    s3 = boto3.client(
        "s3",
        aws_access_key_id=var.s3_access,
        aws_secret_access_key=var.s3_secret
    )
    buffer = io.BytesIO()
    try:
        s3.download_fileobj(var.bucket, f'recordings/{uuid}.mp4', buffer)
    except NoCredentialsError:
        return {"error": "Invalid S3 credentials"}, 401
    except Exception as e:
        return {"error": str(e)}, 500

    buffer.seek(0)  # ensure you're at the start of the file.
    size = buffer.getbuffer().nbytes  # get the file size from buffer

    # range headers are for seeking
    range_header = request.headers.get('Range', None)
    download = request.args.get('download', None)
    disposition = "attachment" if download else "inline"

    if not range_header:
        rv = Response(buffer.read(), 200, mimetype='audio/mp4',
                      content_type='audio/mp4', direct_passthrough=True)
        rv.headers.add('Content-Disposition', f'{disposition}; filename={uuid}.mp4')
        rv.headers.add('Content-Type', 'audio/mp4')
        return rv

    byte1, byte2 = 0, None

    # parse range header
    m = re.search('(\d+)-(\d*)', range_header)
    g = m.groups()

    if g[0]: byte1 = int(g[0])
    if g[1]: byte2 = int(g[1])

    length = size - byte1 if byte2 is None else byte2 - byte1 + 1
    buffer.seek(byte1)

    rv = Response(buffer.read(length), 206, mimetype='audio/mp4',
                  content_type='audio/mp4', direct_passthrough=True)
    rv.headers.add('Content-Range', f'bytes {byte1}-{byte1+length-1}/{size}')
    rv.headers.add('Content-Disposition', f'{disposition}; filename={uuid}.mp4')
    rv.headers.add('Content-Type', 'audio/mp4')

    return rv

# Functions to serve from on-disk files
# @app.route("/audio/<uuid>")
# def streamaudio(uuid):
#     def generate():
#         with open(f"{var.recdir}/{uuid}.mp4", "rb") as faudio:
#             data = faudio.read(1024)
#             while data:
#                 yield data
#                 data = faudio.read(1024)
#     return Response(generate(), mimetype="video/mp4")

# @app.route('/dl/<uuid>', methods=['GET'])
# def download(uuid):
#     return send_from_directory(directory=var.recdir, 
#         path=f'{uuid}.mp4')

@app.route('/search', methods=['GET'])
def search_data():
    if 'username' not in session:
        return redirect(url_for('login'))
    args = request.args
    key = args.get('key')
    value = args.get('value')
    starttime = args.get('starttime')
    endtime = args.get('endtime')
    if key == 'phone':
        value = indexer.sanitize_phone(value)
    js_object = json.loads(json.dumps(
        indexer.searcher(key,value,starttime,endtime),
        sort_keys=True, default=str))
    if js_object['data'] == []:
        return render_template('empty.html')
    flattened_data = [item for sublist in js_object['data'] for item in sublist]
    df = pd.json_normalize(flattened_data)
    df['timestamp'] = df['timestamp'].astype(str)
    return render_template('index.html', data=df)

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    js_object = json.loads(json.dumps(indexer.get_data(),
        sort_keys=True, default=str))
    flattened_data = [item for sublist in js_object['data'] for item in sublist]
    df = pd.json_normalize(flattened_data)
    df['timestamp'] = df['timestamp'].astype(str)
    return render_template('index.html', data=df)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if indexer.validate_user(username, password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid username or password")
    else:
        return render_template('login.html')

@app.route('/admin', methods=['GET'])
def admin():
    if 'username' not in session or session['username'] != 'admin':
        abort(403)
    users = indexer.get_users()
    js_object = json.loads(json.dumps(indexer.get_data(),
        sort_keys=True, default=str))
    flattened_data = [item for sublist in js_object['data'] for item in sublist]
    df = pd.json_normalize(flattened_data)
    df['timestamp'] = df['timestamp'].astype(str)
    return render_template('admin.html', users=users, data=df)

@app.route('/admin/delete/<username>', methods=['POST'])
def delete(username):
    if 'username' not in session or session['username'] != 'admin':
        abort(403)
    if indexer.delete_user(username):
        return redirect(url_for('admin'))
    else:
        return "Error: User not found", 404

@app.route('/admin/update', methods=['POST'])
def update():
    if 'username' not in session or session['username'] != 'admin':
        abort(403)
    username = request.form.get('username')
    password = request.form.get('password')
    if username and password:
        if indexer.update_user(username, password):
            return redirect(url_for('admin'))
    return "Error: User not found or invalid password", 400

@app.route('/admin/add', methods=['POST'])
def add_user():
    if 'username' not in session or session['username'] != 'admin':
        abort(403)
    username = request.form.get('username')
    password = request.form.get('password')
    if username and password:
        indexer.create_user(username, password)
        flash('User successfully added')
    else:
        flash('Error: Invalid username or password')
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    if 'username' in session:
        session.pop('username', None)
    return redirect(url_for('index'))

if __name__=="__main__":
    http_server = wsgiserver.WSGIServer(app, host='0.0.0.0', port=8090)
    http_server.start()
