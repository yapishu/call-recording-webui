import os
from datetime import datetime
from uuid import uuid1
from pydub import AudioSegment
import sqlite3
import var
import boto3
from boto3 import session
from botocore.exceptions import ClientError
from botocore.client import Config
from werkzeug.security import generate_password_hash, check_password_hash

if var.if_s3 == 'yes':
    s3 = boto3.client(
        "s3",
        aws_access_key_id=var.s3_access,
        aws_secret_access_key=var.s3_secret
    )

os.popen(f'chown -R 1001:1001 {var.recdir}')

# Create DB of file IDs and users
db_path = f'{var.recdir}/db.sq3'
db = sqlite3.connect(db_path, isolation_level=None,
    detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
db.execute('pragma journal_mode=wal;')
db.execute('CREATE TABLE IF NOT EXISTS files (id INTEGER NOT NULL, \
            uuid TEXT NULL, ext TEXT NULL, phone TEXT NULL, \
            timestamp TIMESTAMP NULL, \
            PRIMARY KEY ("id" AUTOINCREMENT) );')
db.execute('CREATE TABLE IF NOT EXISTS users ( \
            id INTEGER NOT NULL, \
            username TEXT NOT NULL, \
            password TEXT NOT NULL, \
            PRIMARY KEY ("id" AUTOINCREMENT) );')
db.commit()
db.close()

# create a webapp user
def create_user(username, password):
    password_hash = generate_password_hash(password)
    conn = sqlite3.connect(db_path, isolation_level=None,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    query = '''INSERT INTO users (username, password) VALUES (?, ?);'''
    cur = conn.cursor()
    cur.execute(query, (username, password_hash))
    conn.commit()

# validate a login
def validate_user(username, password):
    conn = sqlite3.connect(db_path, isolation_level=None,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    query = '''SELECT password FROM users WHERE username = ?;'''
    cur = conn.cursor()
    cur.execute(query, (username,))
    result = cur.fetchone()
    # create admin user on first login if it doesnt exist
    if username == 'admin' and result is None:
        create_user(username,password)
        return check_password_hash(result[0], password)
    elif result is None:
        return False
    return check_password_hash(result[0], password)

# return user list
def get_users():
    conn = sqlite3.connect(db_path, isolation_level=None,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE username <> 'admin'")
    users = c.fetchall()
    conn.close()
    return users

def delete_user(username):
    if username != 'admin':
        conn = sqlite3.connect(db_path, isolation_level=None,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()
        conn.close()

# reset pw
def update_user(username, password):
    if username != 'admin':
        hashed_password = generate_password_hash(password, method='sha256')
        conn = sqlite3.connect(db_path, isolation_level=None,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        c = conn.cursor()
        c.execute("UPDATE users SET password=? WHERE username=?", (hashed_password, username))
        conn.commit()
        conn.close()

# sanitize phone number inputs
def sanitize_phone(phone):
    removers = ['(',')','-','.',' ','	']
    for char in removers:
        phone.replace(char,'')
    if len(phone) == 10:
        phone = f'+{var.ccode}' + phone
    elif len(phone) > 10 and phone[0] != '+':
        phone = '+' + phone
    return phone

# return dict of values
def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

# add a recording to db
def add_file(uuid,ext,phone,timestamp):
    if len(phone) == 10:
        phone = f'+{var.ccode}' + phone
    conn = sqlite3.connect(db_path, isolation_level=None,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    query = f'INSERT INTO files VALUES (?,?,?,?,?);'
    cur = conn.cursor()
    cur.execute(query, (None,uuid,ext,phone,timestamp))
    conn.commit()

# get all unique extensions for main page
def get_exts():
    query = 'SELECT DISTINCT ext FROM files ORDER BY ext;'
    conn = sqlite3.connect(db_path, isolation_level=None,
    detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = dict_factory
    cur = conn.cursor()
    answer_raw = cur.execute(query).fetchall()
    return answer_raw

# get all of something
def get_vals(key):
    query = f'SELECT {key} FROM files ORDER BY {key};'
    conn = sqlite3.connect(db_path, isolation_level=None,
    detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = dict_factory
    cur = conn.cursor()
    answer_raw = cur.execute(query).fetchall()
    return answer_raw

# get all data from matching rows
def get_row(key,value):
    query = f'SELECT uuid,ext,phone,timestamp FROM files WHERE {key} = {value};'
    conn = sqlite3.connect(db_path, isolation_level=None,
    detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = dict_factory
    cur = conn.cursor()
    answer_raw = cur.execute(query).fetchall()
    return answer_raw

# get count of rows in table
def get_count():
    query = 'SELECT COUNT(*) from files;'
    conn = sqlite3.connect(db_path, isolation_level=None,
    detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = dict_factory
    cur = conn.cursor()
    answer_raw = cur.execute(query).fetchall()
    return answer_raw[0]['COUNT(*)']

# generate data for main page
def get_data():
    result = {'data':[]}
    ids = []
    for res in get_exts():
        uid = res['ext']
        ids.append(uid)
    uids = list(dict.fromkeys(ids))
    uidlen = len(uids)
    total_count = get_count()
    counter = total_count
    if total_count > 100:
        while counter > total_count - 100:
            result['data'].append(get_row('id',counter))
            counter -= 1
    else:
        while counter > 0:
            result['data'].append(get_row('id',counter))
            counter -= 1
    # while counter < total_count and counter < 100:
    #     result['data'].append(get_row('ext',uids[counter]))
    #     counter += 1
    return result

# build search results from db
# indexer.searcher('ext','1011','2023-04-25T00:00','2023-05-03T23:59')
def searcher(key,value,starttime,endtime):
    if len(starttime) < 3:
        starttime = '2023-04-28T00:00'
    if len(endtime) < 3:
        endtime = '2030-12-31T00:00'
    if len(value) > 2:
        query = f'SELECT id FROM files WHERE {key} = "{value}" \
            AND timestamp >= strftime(\'%Y-%m-%dT%H:%M\',?) AND \
            timestamp <= strftime(\'%Y-%m-%dT%H:%M\',?) ORDER BY timestamp;'
    elif len(value) <= 2:
        query = f'SELECT id FROM files WHERE \
            timestamp >= strftime(\'%Y-%m-%dT%H:%M\',?) AND \
            timestamp <= strftime(\'%Y-%m-%dT%H:%M\',?) ORDER BY timestamp;'
    conn = sqlite3.connect(db_path, isolation_level=None,
    detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = dict_factory
    cur = conn.cursor()
    answer_raw = cur.execute(query, (starttime,endtime)).fetchall()
    result = {'data':[]}
    ids = []
    for res in answer_raw:
        uid = res['id']
        ids.append(uid)
    uids = list(dict.fromkeys(ids))
    uidlen = len(uids)
    counter = 0
    while counter < uidlen:
        result['data'].append(get_row('id',uids[counter]))
        counter += 1
    return result

# upload files to s3 -- skip existing mp4's, overwrite everything else
def s3_upload(filepath, acl="bucket-owner-full-control"):
    filename = os.path.basename(filepath)
    if filepath == '/opt/recs/db.sq3':
        contenttype = 'application/x-sqlite3'
    elif '.mp4' in filepath:
        contenttype = 'audio/mp4'
        try:
            s3.head_object(Bucket=var.bucket, Key=f'recordings/{filename}')
            return
        except:
            try:
                s3.upload_file(
                    filepath,
                    var.bucket,
                    f'recordings/{filename}',
                    ExtraArgs={
                        "ACL": acl,
                        "ContentType": contenttype
                    }
                )
            except Exception as e:
                print("Error uploading: ", e)
                return e
    else:
        contenttype = 'application/octet-stream'
    try:
        s3.upload_file(
            filepath,
            var.bucket,
            f'recordings/{filename}',
            ExtraArgs={
                "ACL": acl,
                "ContentType": contenttype
            }
        )
    except Exception as e:
        print("Error uploading: ", e)
        return e
    if 'db.sq3' not in filepath:
        try:
            os.remove(filepath)
            print(f"{filepath} deleted from disk.")
        except OSError as e:
            print(f"Error deleting {filepath}: {e}")
    return filename


# bulk import new wav files
def importer():
    # extlist = os.listdir(var.recdir)
    extlist = [d for d in os.listdir(var.recdir) if os.path.isdir(f'{var.recdir}/{d}')]
    for ext in extlist:
        wavlist = os.listdir(f'{var.recdir}/{ext}')
        for wav in wavlist:
            if '.wav' in wav:
                phone = wav.split('-')[1].split('_')[0]
                ts = wav.split('-')[1].split('_')[1].split('(')[0]
                timestamp = datetime.strptime(ts, "%Y%m%d%H%M%S")
                print(f'{ext}:{phone} @ {timestamp}')
                rndname = str(uuid1())
                audio = AudioSegment.from_wav(f'{var.recdir}/{ext}/{wav}')
                audio.export(f"{var.recdir}/{rndname}.mp4", format="mp4", parameters=["-b:a","96k"])
                add_file(rndname,ext,phone,timestamp)
                if var.if_s3 == 'yes':
                    s3_upload(f"{var.recdir}/{rndname}.mp4")
                os.remove(f'{var.recdir}/{ext}/{wav}')
    if var.if_s3 == 'yes':
        s3_upload(f"{var.recdir}/db.sq3")
