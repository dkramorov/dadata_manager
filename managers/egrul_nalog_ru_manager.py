#-*- coding:utf-8 -*-
import requests

from managers.simple_logger import logger


class EgrulNalogRuManager:
    """Работа с egrul.nalog.ru
       Не работает с зарубежных ip адресов
       # proxies = {'http': 'socks5://10.10.9.1:3333', 'https': 'socks5://10.10.9.1:3333'}
       # proxies = {'http': 'http://10.10.9.1:3128', 'https': 'https://10.10.9.1:3128'}
    """
    host = 'https://egrul.nalog.ru/'
    user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:147.0) Gecko/20100101 Firefox/147.0'

    def __init__(self, proxies: dict = None):
        self.proxies = None
        if self.proxies:
            self.proxies = proxies

    @property
    def headers(self):
        """Заголовки для запросов"""
        return {
            'User-Agent': self.user_agent,
        }

    def get_by_inn(self, inn: str):
        """Получение данные по ИНН
           :param inn: ИНН
        """
        result = {}
        if not inn:
            return result
        params = {
            'vyp3CaptchaToken': '',
            'page': '',
            'query': inn,
            'region': '',
            'PreventChromeAutocomplete': '',
        }
        s = requests.Session()
        r = s.post(self.host, data=params, headers=self.headers, proxies=self.proxies)
        resp = r.json()
        r = s.get('%ssearch-result/%s' % (self.host, resp['t']), headers=self.headers, proxies=self.proxies)
        resp = r.json()
        rows = resp.get('rows', [])
        if rows:
            row = rows[0]
            result = {
                'address': row.get('a', ''),
                'name': row.get('c', ''),
                'director': row.get('g', ''),
                'inn': row.get('i', ''),
                'type': row.get('k', ''),
                'full_name': row.get('n', ''),
                'ogrn': row.get('o', ''),
                'kpp': row.get('p', ''),
                'reg': row.get('r', ''),
            }
        return result
