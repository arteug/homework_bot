import os
import sys
import time
import logging
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import InvalidResponseCodeException

load_dotenv()

logger = logging.getLogger('logger')
logger.setLevel(logging.DEBUG)
logger_formatter = logging.Formatter('%(asctime)s - %(name)s [%(levelname)s] '
                                     '%(funcName)s - %(lineno)d - %(message)s')

file_handler = logging.FileHandler(
    os.path.join(
        os.path.abspath(__file__), f'{__file__}.log'),
    encoding='utf-8'
)
file_handler.setLevel(logging.DEBUG)

file_handler.setFormatter(logger_formatter)
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(logger_formatter)
logger.addHandler(stream_handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Check environment variables."""
    tokens = (('PRACTICUM_TOKEN', PRACTICUM_TOKEN),
              ('TELEGRAM_TOKEN', TELEGRAM_TOKEN),
              ('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID))
    all_tokens_present = True
    missing_tokens = []
    for token_name, token_value in tokens:
        if not token_value:
            all_tokens_present = False
            missing_tokens.append(token_name)
    if not all_tokens_present:
        logger.critical(f'Отсутствуют следующие токены: '
                        f'{", ".join(missing_tokens)}')
        raise KeyError('Not all tokens are present.')


def send_message(bot, message):
    """Send a message to TG chat."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telebot.ExceptionHandler as e:
        logger.error(f'Failed to send message to '
                     f'chat_id {TELEGRAM_CHAT_ID}, {e}')
        return False
    logger.debug(f'Sent message to chat_id {TELEGRAM_CHAT_ID}')
    return True


def get_api_answer(timestamp):
    """Get info from YANDEX API."""
    request_data = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    logger.info('Request to YANDEX api, url: {url}, '
                'headers: {headers}, '
                'params: {params}'.format(**request_data))
    try:
        response = requests.get(**request_data)
    except requests.RequestException as e:
        raise ConnectionError(
            'Exception {e} occurred while request to YA_API with '
            'url: {url}, headers: {headers}, params: {params}'
            .format(e, **request_data))
    if response.status_code != HTTPStatus.OK:
        raise InvalidResponseCodeException(
            f'Yandex API returned {response.status_code}, '
            f'reason: {response.reason}, '
            f'response text: {response.text}')
    return response.json()


def check_response(response):
    """Check response from YANDEX API for containing keys."""
    if not isinstance(response, dict):
        raise TypeError('Response is not a dictionary')
    if 'homeworks' not in response:
        raise KeyError('Failed to get "homeworks" in response JSON object')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('"response[homeworks]" is not a list]"')
    return homeworks


def parse_status(homework):
    """Parse homework statuses and prepare string to send to Telegram."""
    if 'status' not in homework:
        raise KeyError('Failed to get " homework status" in response object')
    if homework['status'] not in HOMEWORK_VERDICTS:
        raise ValueError(f'Unknown homework status: {homework["status"]}')
    if 'homework_name' not in homework:
        raise KeyError('"homework_name" key not found.')
    verdict = HOMEWORK_VERDICTS.get(homework['status'])
    homework_name = homework['homework_name']
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Main function."""
    check_tokens()
    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_report = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logger.debug('No homeworks found for now')
                continue
            homework = homeworks[0]
            verdict = parse_status(homework)
            if verdict != previous_report and send_message(bot, verdict):
                previous_report = verdict
                timestamp = response.get('timestamp', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            current_report = message
            logger.error(message)
            if (current_report != previous_report
                    and send_message(bot, message)):
                previous_report = current_report
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
