import os
import sys
import time
import logging

import requests
from dotenv import load_dotenv
from telebot import TeleBot

load_dotenv()

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s] %(message)s',
                    filename='main.log')

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

PREVIOUS_STATUS = ''


def check_tokens():
    """Check environment variables."""
    if None not in (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, PRACTICUM_TOKEN):
        return True
    else:
        logging.critical('Required environment variables are missing '
                         'to launch the bot')
        return False


def send_message(bot, message):
    """Send a message to TG chat."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        logging.error(f'Failed to send message to '
                      f'chat_id {TELEGRAM_CHAT_ID}, {e}')
        return e
    logging.debug(f'Sent message to chat_id {TELEGRAM_CHAT_ID}')


def get_api_answer(timestamp):
    """Get info from YANDEX API."""
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params={'from_date': timestamp})
    except requests.RequestException as e:
        logging.error(f'Failed to get answer for {ENDPOINT}')
        return f'Exception occurred while requesting YANDEX API, {e}'
    if response.status_code != 200:
        raise Exception(f'Yandex API returned {response.status_code}')
    return response.json()


def check_response(response):
    """Check response from YANDEX API for containing keys."""
    if not isinstance(response, dict):
        print(isinstance(response, dict))
        raise TypeError('Response is not a dictionary')
    if 'homeworks' not in response:
        logging.error('Failed to get "homeworks" in response JSON object')
        raise KeyError('Failed to get "homeworks" in response JSON object')
    if not isinstance(response['homeworks'], list):
        raise TypeError('"response[homeworks]" is not a list]"')
    return True


def parse_status(homework):
    """Parse homework statuses and prepare string to send to Telegram."""
    global PREVIOUS_STATUS
    print(homework)
    if 'homework_name' not in homework:
        logging.error('Missing "homework_name" in homework')
        raise KeyError('"homework_name" key not found.')
    if homework['status'] not in HOMEWORK_VERDICTS.keys():
        logging.error(f'Homework status {homework["status"]} not recognized')
        raise KeyError(f'Unknown homework status: {homework["status"]}')
    verdict = HOMEWORK_VERDICTS.get(homework['status'])
    homework_name = homework['homework_name']
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Main function."""
    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    if check_tokens():
        while True:
            try:
                response = get_api_answer(timestamp)
                if check_response(response):
                    if len(response['homeworks']):
                        message = parse_status(response['homeworks'][0])
                        if message:
                            send_message(bot, message)
                    else:
                        logging.debug('Empty homework list in response')
                        raise Exception('No homeworks found from this period.')
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                send_message(bot, message)
            time.sleep(RETRY_PERIOD)
    else:
        logging.critical('Not enough environment variables')
        sys.exit(1)


if __name__ == '__main__':
    main()
