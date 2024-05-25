FROM python:3.11-slim

WORKDIR /podcasticot

COPY server.py requirements.txt /podcasticot/
COPY templates/ /podcasticot/templates/
COPY static/ /podcasticot/static/
COPY business/ /podcasticot/business/
COPY persistence/ /podcasticot/persistence/

RUN pip install -r requirements.txt --no-cache-dir

EXPOSE 80

CMD ["gunicorn", "server:app", "-b", "0.0.0.0:80", "-w", "4"]
