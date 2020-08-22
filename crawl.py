import json
import os
import time
import datetime
import requests
from bs4 import BeautifulSoup as bs4

CHAT_ID = os.environ['CHAT_ID']
TOKEN = os.environ['TOKEN']
BOT_URL = os.environ['BOT_URL']
TIMEOUT = int(os.environ.get('CRAIG_TIMEOUT', 600))
MAX_NUMBER = int(os.environ.get('MAX_NUMBER', 100000))
MAX_PRICE = int(os.environ.get('MAX_PRICE') or 3000)
MAX_DISTANCE = int(os.environ.get('MAX_DISTANCE') or 2)
ZIP = os.environ.get('ZIP') or 94121
SKIP_WO_IMAGES = True
RES_FILE_LOC = "res/result.txt"
URL = os.environ.get('URL') or f'https://sfbay.craigslist.org/d/apts-housing-for-rent/search/apa'
DIRECT_URL = os.environ.get('DIRECT_URL') or None


def _send_request(method_name, payload):
    """
    Method to send requests defined in method_name to telegram bot.
    :param method_name: method to send
    :param payload: payload to send
    :return: json response
    """
    uri = "{bot_url}/{method_name}".format(bot_url=BOT_URL, method_name=method_name)
    r = requests.post(uri, json=payload)
    if r.status_code == 429:
        resp = json.loads(r.text)
        time.sleep(resp['parameters']['retry_after']+1)
        rr = requests.post(uri, json=payload)
        rr.raise_for_status()
        return rr.json()
    r.raise_for_status()
    return r.json()


def _send_message(chat_id, text):
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    return _send_request("sendMessage", payload)


def _send_media_group(chat_id, images):
    payload = {
        "chat_id": chat_id,
        "media": [{"type": "photo", "media": url} for url in images],
    }
    return _send_request("sendMediaGroup", payload)


def parse_size(size):
    split = size.strip('\n ').split('-')
    n_brs = None
    size = None
    if len(split) == 2:
        if 'br' in split[0]:
            n_brs = split[0]
        elif 'br' in split[1]:
            n_brs = split[1]
        else:
            n_brs = 0
        if 'ft2' in split[0]:
            size = split[0]
        elif 'ft2' in split[1]:
            size = split[1]
        else:
            size = 0
    elif 'br' in split[0]:
        # It's the n_bedrooms
        n_brs = split[0].replace('br', '')
        size = 0
    elif 'ft2' in split[0]:
        # It's the size
        size = split[0].replace('ft2', '')
        n_brs = 0
    return n_brs, size


def crawl():
    res = {}
    offset = 0
    if DIRECT_URL:
        target_url = DIRECT_URL
        params = dict(s=offset)
    else:
        target_url = URL
        params = dict(max_price=MAX_PRICE, hasPic=1, bundleDuplicates=1, search_distance=MAX_DISTANCE, postal=ZIP,
                      s=offset)
    while True:
        params["s"] = offset
        rsp = requests.get(target_url, params=params)
        print("{}: Requesting {}".format(datetime.datetime.now(), rsp.url))
        html = bs4(rsp.text, 'lxml')
        apts = html.find_all('li', attrs={'class': 'result-row'})
        num_apts = len(apts)
        print("Got {} results".format(num_apts))
        if not apts:
            print("All results processed".format(num_apts))
            break
        else:
            print(f"Processing results with OFFSET {offset}")
            offset += num_apts
        for apt in apts:
            try:
                title = apt.find('a', attrs={'class': 'hdrlnk'}).text
                url = apt.find('a', attrs={'class': 'hdrlnk'}).attrs['href']
                img_ids = apt.find('a').attrs['data-ids'].split(',')
                imgs = ["https://images.craigslist.org/" + img.split(":")[1] + "_300x300.jpg" for img in img_ids]
                if SKIP_WO_IMAGES and not imgs:
                    continue
                if not res.get(url):
                    parsed_res = {
                        'time': apt.find('time')['datetime'],
                        'price': float(apt.find('span', {'class': 'result-price'}).text.strip('$').replace(',','')),
                        'url': url,
                        'hood': apt.find('span', attrs={'class': 'result-hood'}).text,
                        'pics': imgs
                    }
                    housing = apt.find('span', attrs={'class': 'housing'})
                    if housing:
                        n_bdrs, size = parse_size(housing.text)
                        parsed_res['n_bdrs'] = n_bdrs
                        parsed_res['size'] = size
                    else:
                        parsed_res['n_bdrs'] = 0
                        parsed_res['size'] = 0
                    res[url] = parsed_res
            except Exception as ex:
                print(ex)
    return res


if __name__ == '__main__':
    if not os.path.isdir('res'):
        os.mkdir('res')
    while True:
        res = crawl()
        if os.path.isfile(RES_FILE_LOC):
            with open(RES_FILE_LOC, mode='r') as f:
                saved_result = f.readlines()[0]
                saved_result = json.loads(saved_result)
        else:
            print("No previous results was found. Creating new set of listings.")
            saved_result = {}
        diff = set(res.keys()).difference(set(saved_result.keys()))
        num_diff = len(diff)
        if diff:
            print("Found {} new listings:".format(num_diff))
        else:
            print("No new listings were found.")
        if num_diff > MAX_NUMBER:
            print("Looks like this is new run, skipping send to to spam chat")
        else:
            for diff_item in diff:
                r = requests.get(res[diff_item]['url'])
                if r.status_code < 399:
                    msg = '{} {} {}'.format(res[diff_item]['url'], res[diff_item]['hood'], res[diff_item]['price'])
                    if res[diff_item].get('n_bdrs'):
                        msg += ' bedrooms: {}'.format(res[diff_item].get('n_bdrs'))
                    if res[diff_item].get('size'):
                        msg += ' size: {}'.format(res[diff_item].get('size'))
                    print(msg)
                    try:
                        _send_message(CHAT_ID, msg)
                    except requests.exceptions.HTTPError as ex:
                        if ex.response.status_code == 429:
                            _send_message(CHAT_ID, msg)
                        print("Was not able to send message to Telegram: %s" % str(ex))
                    if len(diff) < MAX_NUMBER:
                        num_of_pic = len(res[diff_item]['pics'])
                        try:
                            if num_of_pic > 1:
                                if num_of_pic > 10:
                                    _send_media_group(CHAT_ID, res[diff_item]['pics'][:5])
                                else:
                                    _send_media_group(CHAT_ID, res[diff_item]['pics'])
                            else:
                                print("Less than 1 pic. Skipping to send")
                        except requests.exceptions.HTTPError as ex:
                            print("Was not able to send media to Telegram: %s" % str(ex))
                    else:
                        print("To much results `%s`, skipping send pic not to spam" % len(diff))
                    time.sleep(1)
                else:
                    print(diff_item, "returns non 200 response code: %s: `%s`" % (res[diff_item]['url'], r.status_code))
        with open(RES_FILE_LOC, mode='w') as f:
            json.dump(res, f)
            f.close()
        print("Going to sleep: {} seconds.".format(TIMEOUT))
        time.sleep(TIMEOUT)
