FROM python:3

RUN mkdir -p /srv/craiglist/

COPY ./requirements.txt /srv/craiglist/
COPY ./crawl.py /srv/craiglist/

RUN pip install --no-cache-dir -r /srv/craiglist/requirements.txt

CMD ["python /srv/craiglist/crawl.py"]
