import config
import requests
import telebot
from bs4 import BeautifulSoup
import re


bot = telebot.TeleBot(config.access_token)


if __name__ == '__main__':
    bot.polling(none_stop=True)
