import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORKS = 'homeworks'
HOMEWORK_NAME = 'homework_name'
STATUS = 'status'


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


def check_tokens():
    """Проверяет токены."""
    for token in [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]:
        if not token:
            logger.critical(
                f'Программа остановлена.'
                f'Отсутствует обязательная переменная окружения {token}.'
            )
            raise SystemExit


def send_message(bot, message):
    """Отправляет сообщения в чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Сообщение в Telegram отправлено: {message}')
    except Exception:
        logger.error(f'Сообщение в {message} не отправлено.')
        raise Exception(f'Сообщение в {message} не отправлено.')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as error:
        error_message = f'Код ответа API: {error}'
        logger.error(error_message)
        raise requests.exceptions.RequestException(error_message)
    finally:
        if response.status_code != HTTPStatus.OK:
            error_message = (
                f'Эндпоинт не доступен, статус: {response.status_code}'
            )
            logger.error(error_message)
            raise requests.exceptions.HTTPError(error_message)
    return response.json()


def check_response(response):
    """Проверяет содержимое ответа от API."""
    if not isinstance(response, dict):
        error_text = (
            f'Тип ответа от api не dict. Неверный тип: {type(response)}'
        )
        logger.error(error_text)
        raise TypeError(error_text)
    if HOMEWORKS not in response:
        error_text = 'В ответе от API нет объекта homeworks'
        logger.error(error_text)
        raise TypeError(error_text)
    if not isinstance(response[HOMEWORKS], list):
        error_text = 'Объект ответа homeworks не является списком'
        logger.error(error_text)
        raise TypeError(error_text)
    return response[HOMEWORKS]


def parse_status(homework):
    """Проверяет не изменился ли статус."""
    if HOMEWORK_NAME not in homework:
        raise KeyError('В домашней работе отсутствует объект homework_name')
    if STATUS not in homework:
        raise Exception('В домашней работе отсутствует объект status')
    homework_name = homework[HOMEWORK_NAME]
    homework_status = homework[STATUS]
    if homework_status not in HOMEWORK_VERDICTS:
        raise Exception(f'Неизвестный статус: {homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)[0]
            message = parse_status(homework)
            send_message(bot, message)
            logging.info(homework)
            current_timestamp = response.get('current_date')
        except IndexError:
            send_message(bot, message)
            logging.info('Статус работы не изменился')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)
        logging.info(f'Сообщение {message} отправлено'.format(message))


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(message)s,'
               '%(name)s, %(funcName)s, %(lineno)d'
    )

    file_handler = RotatingFileHandler(
        'main.log',
        mode='a',
        maxBytes=50000,
        backupCount=5
    )

    main()
