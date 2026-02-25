import datetime
import logging
import os
import re
import requests
import time

from envparse import env
from managers.simple_logger import logger


env.read_envfile()


class MockSettings:
    FULL_SETTINGS_SET = os.environ


try:
    from django.conf import settings
    hasattr(settings, 'DEBUG')
except Exception as e:
    logger.info('Exception from django.conf import settings: %s' % e)
    settings = MockSettings()


rega_colons = re.compile('[:]+', re.U+re.I+re.DOTALL)
rega_int = re.compile('[^0-9]', re.U+re.I+re.DOTALL)
rega_spaces = re.compile('[ ]+', re.U+re.I+re.DOTALL)


class DadataManager:
    """Работа с Dadata
       https://dadata.ru/api/find-party/
    """
    host = settings.FULL_SETTINGS_SET.get('DADATA_SUGGESTION_BASE_URL') or 'https://suggestions.dadata.ru'
    api_key = settings.FULL_SETTINGS_SET.get('DADATA_API_KEY')
    secret_key = settings.FULL_SETTINGS_SET.get('DADATA_SECRET_KEY')

    def __init__(self,
                 host: str = None,
                 api_key: str = None,
                 secret_key: str = None):
        if host:
            self.host = host

        self.host = self.host.rstrip()
        if api_key:
            self.api_key = api_key
        if secret_key:
            self.secret_key = secret_key

    def get_headers(self):
        """Заголовки для запроса"""
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': 'Token %s' % self.api_key,
        }

    def get_by_inn_or_ogrn(self, inn_or_ogrn: str):
        """Получение организации по ИНН / ОГРН
           https://dadata.ru/api/find-party/
        """
        endpoint = '/suggestions/api/4_1/rs/findById/party'
        url = '%s%s' % (self.host, endpoint)
        r = requests.post(url, headers=self.get_headers(), json={'query': inn_or_ogrn})
        return r.json()

    @staticmethod
    def get_main_org_from_suggestions(resp: dict):
        """Находит головной офис в компании
           :param resp: ответ от дадаты по get_by_inn_or_ogrn
        """
        if not isinstance(resp, dict):
            return None
        main_org = None
        for org in resp.get('suggestions', []):
            # Первая встретившаяся организация как головной офис
            if not main_org:
                main_org = org['data']
            # Главная организация
            if org['data'].get('branch_type') == 'MAIN':
                return org['data']
        return main_org

    def search_address(self,
                       query: str,
                       count: int = 10,
                       language: str = 'RU',  # EN
                       division: str = 'ADMINISTRATIVE',  # MUNICIPAL
                       locations: list = None,
                       locations_geo: list = None,
                       locations_boost: list = None,
                       from_bound: dict = None,
                       to_bound: dict = None):
        """Получение адреса по параметрам
           https://dadata.ru/api/suggest/address/
           ISO коды https://ru.wikipedia.org/wiki/ISO_3166-2:RU
           :param query: запрос, обязательное поле
                         "query": "московское шоссе",
           :param count: кол-во, максимум 20
           :param language: язык - RU/EN
           :param division: Деление - Административное/Муниципальное
           :param locations: ограничение по родителю
                             "locations": [{"country_iso_code": "BY", "region_iso_code": "BY-BR"}]
                             "locations": [{"fias_id": "110d6ad9-0b64-47cf-a2ee-7e935228799c"}]
                             Можно фильтровать по iso кодам страны и региона
                             'country_iso_code': 'RU',
                             'region_iso_code': 'RU-IRK',
                             Можно фильровать по fias_id
                             area_fias_id, city_district_fias_id, flat_fias_id,
                             street_fias_id, room_fias_id, stead_fias_id
                             "region_fias_id": "6466c988-7ce3-45e5-8b97-90ae16cb1249" # Иркутская область
                             "city_fias_id": "8eeed222-72e7-47c3-ab3a-9a553c31cf72" # Иркутск
                             "settlement_fias_id": "88c1ece6-d2aa-4d2f-9d68-d85a15eea279" # м-н Юбилейный
                             "house_fias_id": "242b97c3-72d9-454a-a3cb-96bd30f2b237" # дом 29
           :param locations_geo: ограничение по радиусу окружности
                                 "locations_geo": [{
                                     "lat": 59.244634,
                                     "lon": 39.913355,
                                     "radius_meters": 200
                                 }]
           :param locations_boost: Приоритет города при ранжировании (по кладр ид)
                                   "locations_boost": [{"kladr_id": "77"}]
           :param from_bound: Гранулярные подсказки
           :param to_bound: Гранулярные подсказки
                            Гранулярные подсказки:
                            Если задать параметры from_bound и  to_bound,
                            то будут подсказки только для указанных частей адреса
                            "from_bound": {"value": "street"},
                            "to_bound": {"value": "street"},
        """
        endpoint = '/suggestions/api/4_1/rs/suggest/address'
        url = '%s%s' % (self.host, endpoint)
        data = {'query': query}
        if count:
            data['count'] = count
        if language:
            data['language'] = language
        if division:
            data['division'] = division
        if locations:
            data['locations'] = locations
        if locations_geo:
            data['locations_geo'] = locations_geo
        if locations_boost:
            data['locations_boost'] = locations_boost
        if from_bound:
            data['from_bound'] = from_bound
        if to_bound:
            data['to_bound'] = to_bound
        r = requests.post(url, headers=self.get_headers(), json=data)
        return r.json()


    def get_address(self, query: str):
        """Получение адреса
           https://confluence.hflabs.ru/pages/viewpage.action?pageId=312016944
           ФИАС-код до дома (fias_id), только для России (19.7+);
           ФИАС-код квартиры (flat_fias_id), только для России (21.2+);
           кадастровый номер (stead_cadnum, house_cadnum или flat_cadnum) только для России;
           :param query: запрос, обязательное поле
                         "query": "5f96fd6b-b3de-451f-b280-8fedf859e683"
        """
        endpoint = '/suggestions/api/4_1/rs/findById/address'
        url = '%s%s' % (self.host, endpoint)
        r = requests.post(url, headers=self.get_headers(), json={'query': query})
        return r.json()


    def search_country(self, query: str):
        """Поиск страны
           https://dadata.ru/api/suggest/country/
           :param query: запрос, обязательное поле
        """
        endpoint = '/suggestions/api/4_1/rs/suggest/country'
        url = '%s%s' % (self.host, endpoint)
        r = requests.post(url, headers=self.get_headers(), json={'query': query})
        return r.json()


    def search_bank(self, query: str):
        """Поиск банка
           https://dadata.ru/api/suggest/bank/
           :param query: запрос, обязательное поле
        """
        endpoint = '/suggestions/api/4_1/rs/suggest/bank'
        url = '%s%s' % (self.host, endpoint)
        r = requests.post(url, headers=self.get_headers(), json={'query': query})
        return r.json()


    def search_address_by_cadastral_number(self, query: str):
        """Поиск адреса по кадастровому номеру
           38:36:000027:3703
           Кадастровый номер - 2 цифры, кадастровый округ (78 – Санкт-Петербург)
                               2 цифры, кадастровый района (36 – Выборгский)
                               6/7 цифр, код квартала
                               n цифр, кадастровый адрес квартиры
        """
        logger.info('search_address_by_cadastral_number %s' % query)
        cadastral_number = rega_int.sub('', query)

        if len(cadastral_number) < 11:
            raise Exception('Кадастровый номер не может быть меньше 11 цифр: %s' % cadastral_number)
        # Если с двоеточиями, то делаем запрос сразу (пробелы заменяем на одинарные, затем на двоеточия)
        if ':' in query:
            cadastral_number = rega_spaces.sub(' ', query).replace(' ', ':')
            cadastral_number = rega_colons.sub(':', cadastral_number)
            result = self.get_address(query=cadastral_number).get('suggestions', [])
            return result

        result1 = result2 = []
        region = cadastral_number[:2]
        district = cadastral_number[2:4]
        if len(cadastral_number) > 11:
            # Вариант 2:2:7:n
            quarter = cadastral_number[4:11]
            flat = cadastral_number[11:]
            cadastral_number1 = '%s:%s:%s:%s' % (region, district, quarter, flat)
            result1 = self.get_address(query=cadastral_number1).get('suggestions', [])

        # В любом случае ищем такой вариант 2:2:6:n
        quarter = cadastral_number[4:10]
        flat = cadastral_number[10:]
        cadastral_number2 = '%s:%s:%s:%s' % (region, district, quarter, flat)
        result2 = self.get_address(query=cadastral_number2).get('suggestions', [])
        # Если оба варианта найдены, отдаем их
        return result1 + result2

