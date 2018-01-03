import json
import os
import time

import requests
from bs4 import BeautifulSoup as bs4

CHAT_ID = os.environ['CHAT_ID']
TOKEN = os.environ['TOKEN']
BOT_URL = os.environ['BOT_URL']


def _send_request(method_name, payload):
    """
    Method to send requests defined in method_name to telegram bot.
    :param method_name: method to send
    :param payload: payload to send
    :return: json response
    """
    uri = "{bot_url}/{method_name}".format(bot_url=BOT_URL, method_name=method_name)
    r = requests.post(uri, json=payload)
    r.raise_for_status()
    return r.json()


def _send_message(chat_id, text):
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    return _send_request("sendMessage", payload)


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
    url_base = 'https://sfbay.craigslist.org/d/apts-housing-for-rent/search/apa'
    params = dict(max_price=2600, hasPic=1, bundleDuplicates=1, search_distance=2, postal=94118)
    rsp = requests.get(url_base, params=params)
    print("{}: Requesting {}".format(time.time(), rsp.url))
    html = bs4(rsp.text, 'html.parser')
    apts = html.find_all('li', attrs={'class': 'result-row'})
    print("Got {} results".format(len(apts)))
    for apt in apts:
        try:
            title = apt.find('a', attrs={'class': 'hdrlnk'}).text
            if not res.get(title):
                parsed_res = {
                    'time': apt.find('time')['datetime'],
                    'price': float(apt.find('span', {'class': 'result-price'}).text.strip('$')),
                    'url': apt.find('a', attrs={'class': 'hdrlnk'}).attrs['href'],
                    'hood': apt.find('span', attrs={'class': 'result-hood'}).text

                }
                housing = apt.find('span', attrs={'class': 'housing'})
                if housing:
                    n_bdrs, size = parse_size(housing.text)
                    parsed_res['n_bdrs'] = n_bdrs
                    parsed_res['size'] = size
                else:
                    parsed_res['n_bdrs'] = 0
                    parsed_res['size'] = 0
                res[title] = parsed_res
        except Exception as ex:
            print(ex)
    return res


if __name__ == '__main__':

    while True:
        res = crawl()
        if os.path.isfile('result.txt'):
            with open('result.txt', mode='r') as f:
                saved_result = f.readlines()[0]
                saved_result = json.loads(saved_result)
                f.close()
        else:
            print("No previous results was found. Creating new set of listings.")
            saved_result = {}
        diff = set(res.keys()).difference(set(saved_result.keys()))
        if diff:
            print("Found {} new listings:".format(len(diff)))
        else:
            print("No new listings were found.")
        for diff_item in diff:
            msg = '{} {} {}'.format(res[diff_item]['url'], res[diff_item]['hood'], res[diff_item]['price'])
            print(msg)
            _send_message(CHAT_ID, msg)
        os.remove('result.txt')
        with open('result.txt', mode='w') as f:
            json.dump(res, f)
            f.close()
        time.sleep(600)
