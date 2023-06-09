FROM python:3.9-slim-buster
RUN apt update && apt install ffmpeg -y
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING="UTF-8"
COPY ./requirements.txt /app/requirements.txt
RUN pip3 install -r /app/requirements.txt
COPY ./ /app
EXPOSE 8090
ENTRYPOINT ["stdbuf","-oL","python3","-u","/app/app.py"]