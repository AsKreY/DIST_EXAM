FROM python:latest

#COPY . .

RUN apt-get update -y

RUN apt-get install tk -y

RUN pip install -r requirements.txt

CMD ["main.py"]
ENTRYPOINT ["python3"]