import logging
import os
import json
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='error.log',
    filemode='a',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)


def check_tokens():
    """Проверяет токены."""
    for token in [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]:
        if not token:
            logger.critical('Программа остановлена.'
                            'Отсутствует обязательная переменная окружения.')
            raise SystemExit


def send_message(bot, message):
    """Отправляет сообщения в чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(
            f'Сообщение в Telegram отправлено: {message}')
    except telegram.TelegramError as error:
        logger.error(
            f'Сообщение в Telegram не отправлено: {error}')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp
    params = {"from_date": timestamp}

    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
    except requests.exceptions.Timeout:
        error_text = "Ошибка запроса к API Яндекс: превышено время ожидания."
        logger.error(error_text)
        raise ConnectionError(error_text)
    except requests.exceptions.TooManyRedirects:
        error_text = (
            "Ошибка запроса к API Яндекс: очень много перенаправлений."
        )
        logger.error(error_text)
        raise ConnectionError(error_text)
    except requests.exceptions.RequestException as error:
        error_text = f"Ошибка запроса к API Яндекс: {error}"
        logger.error(error_text)
        raise ConnectionError(error_text)

    if homework_statuses.status_code == HTTPStatus.OK:
        logger.debug("Получен ответ со статусом 200 ОК")
        try:
            api_answer_json = homework_statuses.json()
        except json.decoder.JSONDecodeError:
            error_text = "Ошибка преобразования ответа от API в json"
            logger.error(error_text)
            raise ValueError(error_text)
        return api_answer_json
    else:
        error_text = f"Ошибка http запроса: {homework_statuses.status_code}"
        logger.error(error_text)
        raise ValueError(error_text)


def check_response(response):
    """Проверяет содержимое ответа от API."""
    if not isinstance(response, dict):
        error_text = (
            f"Тип ответа от api не dict. Неверный тип: {type(response)}"
        )
        logger.error(error_text)
        raise TypeError(error_text)
    if "homeworks" not in response:
        error_text = "В ответе от API нет объекта homeworks"
        logger.error(error_text)
        raise TypeError(error_text)
    if not isinstance(response["homeworks"], list):
        error_text = "Объект ответа homeworks не является списком"
        logger.error(error_text)
        raise TypeError(error_text)
    return response["homeworks"]


def parse_status(homework):
    """Проверяет не изменился ли статус."""
    try:
        homework_name = homework["homework_name"]
    except KeyError:
        error_text = "В домашней работе отсутствует объект homework_name"
        logger.error(error_text)
        raise KeyError(error_text)
    try:
        homework_status = homework["status"]
    except KeyError:
        error_text = "В домашней работе отсутствует объект status"
        logger.error(error_text)
        raise KeyError(error_text)

    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_status]
        info_text = (
            f'Изменился статус проверки работы "{homework_name}". {verdict}'
        )
        logger.debug(info_text)
        return info_text
    else:
        error_text = f"Неизвестный статус: {homework_status}"
        logger.error(error_text)
        raise ValueError(error_text)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        SystemExit
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            for homework in homeworks:
                if homework:
                    logger.info(
                        'Сообщение об изменении статуса работы отправлено.'
                    )
                    send_message(bot, parse_status(homework))
            logger.info('Статус работы не изменился.')
            time.sleep(RETRY_PERIOD)
            current_timestamp = response.get('current_date')
            response = get_api_answer(current_timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.exception(message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
