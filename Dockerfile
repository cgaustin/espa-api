FROM python:2.7

RUN mkdir -p /home/espadev/espa-api
WORKDIR /home/espadev/espa-api

COPY setup/requirements.txt /home/espadev/espa-api
RUN pip install --no-cache-dir -r requirements.txt

ENV ESPA_CONFIG_PATH=/home/espadev/
ENV ESPA_API_EMAIL_RECEIVE="someone@somewhere.com"
ENV ESPA_ENV="dev"

COPY . /home/espadev/espa-api

EXPOSE 4004
ENTRYPOINT ["uwsgi", "run/api-dev-uwsgi.ini"]
