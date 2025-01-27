import os
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv


def get_token() -> str:
    """Получает токен доступа к API VK из переменных окружения.

    Возвращает:
        str: Токен доступа VK.
    """
    load_dotenv()
    return os.getenv('VK_TOKEN')


def shorten_link(url: str) -> str:
    """Сокращает указанную URL-адрес с помощью API VK.

    Args:
        url (str): URL-адрес для сокращения.

    Returns:
        str: Сокращенный URL-адрес.

    Raises:
        requests.RequestException: При выполнении запроса к API VK.
    """
    token = get_token()
    url_template = 'https://api.vk.com/method/utils.getShortLink'
    version = '5.199'
    params = {
        'access_token': token,
        'v': version,
        'url': url,
    }
    response = requests.get(url_template, params=params)
    response.raise_for_status()
    short_url_data = response.json()
    return short_url_data['response']['short_url']


def count_clikcs(short_url) -> int:
    """Получает статистику кликов для сокращенной ссылки с помощью API VK.

    Args:
        short_url (str): Сокращенная ссылка для получения статистики.

    Returns:
        int: Количество кликов по сокращенной ссылке.

    Raises:
        Exception: При получении статистики или ошибка API VK.
    """
    token = get_token()
    parsed = urlparse(short_url)
    version = '5.199'
    url_template = 'https://api.vk.com/method/utils.getLinkStats'

    params = {
        'access_token': token,
        'v': version,
        'key': parsed.path[1:],
        'interval': 'forever',
    }

    response = requests.get(url_template, params=params)
    response.raise_for_status()
    response_data = response.json()

    if 'error' in response_data:
        raise Exception(f"Ошибка API: {response_data['error']['error_msg']}")

    if 'response' in response_data and 'stats' in response_data['response']:
        stats = response_data['response']['stats']
        if isinstance(stats, list) and len(stats) > 0:
            return stats[0]['views']
        else:
            return 0
    else:
        raise Exception("Ошибка при получении статистики кликов.")
