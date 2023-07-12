import os

# recdir = '/opt/recs'
recdir = os.getenv('RECDIR')
if_s3 = os.getenv('IF_S3')
s3_access = os.getenv('S3_ACCESS')
s3_secret = os.getenv('S3_SECRET')
bucket = os.getenv('S3_BUCKET')
secret_key = os.getenv("SECRET_KEY").encode()
ccode = os.getenv('COUNTRY_CODE')