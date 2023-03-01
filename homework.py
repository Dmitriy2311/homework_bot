import logging
import os
import time
import sys
import requests
import telegram

from http import HTTPStatus
from dotenv import load_dotenv

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


def check_tokens():
    """Проверяет токены."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True


def send_message(bot, message):
    """Отправляет сообщения в чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(
            f'Сообщение в Telegram отправлено: {message}'
        )
    except Exception as error:
        logger.error(
            f'Ошибка при отправке сообщения {error}'
        )


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        logging.error(
            f'Ошибка при запросе к основному API: {error}'
        )
        raise Exception(
            f'Ошибка при запросе к основному API: {error}'
        )
    finally:
        if response.status_code != HTTPStatus.OK:
            error_message = (
                f'Эндпоинт не доступен, статус: {response.status_code}'
            )
            raise requests.exceptions.HTTPError(error_message)
    return response.json()


def check_response(response):
    """Проверяет содержимое ответа от API."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Тип ответа от api не dict. Неверный тип: {type(response)}'
        )
    if HOMEWORKS not in response:
        raise KeyError(
            'В ответе от API нет объекта homeworks'
        )
    homeworks_list = response[HOMEWORKS]
    if not isinstance(homeworks_list, list):
        raise TypeError(
            'Объект ответа homeworks не является списком'
        )
    return homeworks_list


def parse_status(homework):
    """Проверяет не изменился ли статус."""
    if HOMEWORK_NAME not in homework:
        raise KeyError(
            'Ключ homework_name отсутствует в homework'
        )
    if STATUS not in homework:
        raise KeyError(
            'Ключ status отсутствует в homework'
        )
    homework_name = homework[HOMEWORK_NAME]
    homework_status = homework[STATUS]
    if homework_status not in HOMEWORK_VERDICTS:
        raise Exception(
            f'Неизвестный статус: {homework_status}'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Нет переменных окружения')
        sys.exit('Нет переменных окружения')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    previos_message = ''
    last_message = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)[0]
            message = parse_status(homework)
            if previos_message != message:
                send_message(bot, message)
                message = previos_message
            else:
                logging.info('Статус работы не изменился')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != last_message:
                send_message(bot, message)
                last_message = message
        finally:
            time.sleep(RETRY_PERIOD)
        logging.info(f'Сообщение {message} отправлено'.format(message))


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(message)s,'
               '%(name)s, %(funcName)s, %(lineno)d',
        handler=[
            logging.handlers.RotatingFileHandler(
                f'{os.path.dirname(__file__)}/main.log'
            ),
            logging.StreamHandler()
        ])
    main()
