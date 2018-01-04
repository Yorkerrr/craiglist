FROM python:3

RUN mkdir -p /srv/craiglist/

WORKDIR /srv/craiglist/
COPY ./requirements.txt /srv/craiglist/
COPY ./crawl.py /srv/craiglist/
#COPY ./result.txt /srv/craiglist/

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "/srv/craiglist/crawl.py"]
