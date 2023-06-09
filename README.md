# Call recording server

perhaps you are like me and saw that you can run a [3CX PBX](https://www.youtube.com/watch?v=n_1wX7kKx7k) for close to free using aws chime for sip trunking. perhaps you are also like me and noticed that that automatically provisioned debian vps has like 7gb of disk. this repo is a solution to the problem of "well what do i do with all these call recordings then?"

this project is a compose stack that runs an sftp server which shares a volume with a flask webapp. configure 3cx to deposit your recordings on the sftp server and they will automatically be compressed, indexed, uploaded to s3, and searchable via the webui.

to install:

- clone this repo on a vps that has ports 80, 443, and 2222 open
- set a dns record for your server
- set the following env vars in your `.env` file
	- `S3_ACCESS` - aws s3 access key
	- `S3_SECRET` - aws s3 secret key
	- `S3_BUCKET` - name of your aws s3 bucket
	- `SECRET_KEY` (random string for cookies)
	- (i dunno if other s3 providers work but you're probably already on aws anyway)
- edit `Caddyfile` to use your domain where it says `mydomain.com`
- run `docker-compose up -d` to build the stack
- open your domain in a browser to make sure it works
- login with the username `admin` and whatever password you want for the admin user
- go to the `/admin` path to create and manage other non-admin users
- configure 3cx to deposit recordings:

![](https://i.imgur.com/5Ue8bKu.png)

(reporting -> recordings -> location)

3cx will deposit the files once a day; the server will check every 6 hours for new files, add them to a sqlite db, compress to mp4, upload to s3, and serve a searchable list of your files. when you play or download a file from the index, it streams from s3, freeing up your precious disk. ganbatte!

| 3CX is a trademark of 3CX SOFTWARE DMCC. i have no affiliation with 3CX SOFTWARE DMCC. this is an open source project i made for fun. |
| - |
