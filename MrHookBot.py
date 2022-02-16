from xml.etree.ElementTree import TreeBuilder
import config
import requests
import telebot
from bs4 import BeautifulSoup
import re
import time


bot = telebot.TeleBot(config.access_token)


def get_page(question_amount = 24, complexity = 'complexity0') -> str:
    url = f'{config.domain}/random/types1/{complexity}/limit{question_amount}'
    response = requests.get(url)
    web_page = response.text
    return web_page


def parse_questions(web_page) -> tuple:
    soup = BeautifulSoup(web_page, "html5lib")
    questions_info = soup.find_all("div", class_="random_question")

    # Массив с текстами вопросов
    question_texts = [q.find_all(string=True, recursive=False) for q in questions_info]
    for index, q in enumerate(question_texts):
        del q[0:3]
        del q[len(q) - 1]
        for key, value in enumerate(q):
            q[key] = value.strip()
            q[key] = " ".join(value.split())
        while "" in q:
            q.remove("")
        question_texts[index] = "\n".join(q)

    # Массив с ответами
    answers = [q.find_all(string=re.compile("Ответ:")) for q in questions_info]
    for i, ans in enumerate(answers):
        answers[i] = " ".join(ans[0].find_parent("p").text.split())
    
    handouts = [] # Массив с данными о текстовых раздатках
    illustrations = [] # Массив с данными о раздатках (картинках)

    for i in range(len(questions_info)):
        handout = None
        handout = questions_info[i].find_all("div", class_="razdatka")
        if handout:
            handout = handout[0].find_all(string=True, recursive=False)
            for index, value in enumerate(handout):
                handout[index] = value.strip()
                handout[index] = " ".join(value.split())
            while "" in handout:
                handout.remove("")
            handouts.append("Раздаточный материал:\n\n" + "\n".join(handout) + "\n")
        else:
            handouts.append(None)

        imgs = None
        imgs = questions_info[i].find_all("img")
        if imgs:
            if len(imgs) == 1:
                illustrations.append(imgs[0].get('src'))
            else:
                illustrations.append([])
                [illustrations[i].append(img.get('src')) for img in imgs]
        else:
            illustrations.append(None)
        
        alter_answers = None # Данные о зачёте (альтернативных ответах)
        alter_answers = questions_info[i].find_all(string=re.compile("Зачёт"))
        if alter_answers:
            answers[i] += "\n" + " ".join(alter_answers[0].find_parent("p").text.split())

        comment = None # Данные об авторских комментариях к ответам
        comment = questions_info[i].find_all(string=re.compile("Комментарий"))
        if comment:
            answers[i] += "\n\n" + " ".join(comment[0].find_parent("p").text.split())

    return question_texts, handouts, illustrations, answers


received_msg = ['status', 'text', 'chat.id']


@bot.message_handler(commands=['start'])
def get_start(message):
    received_msg[2] = message
    amount_options = ['12', '24', '36', '45', '60', '90']
    markup=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, row_width=3)
    markup.add(*amount_options)
    bot.send_message(message.chat.id, 'Привет! Я умею задавать вопросы из базы спортивного "Что? Где? Когда?".\n\nСколько вопросов Вы хотите отыграть?\n\nВы можете выбрать один из предложенных вариантов, нажав на кнопку, или ввести любое число с помощью клавиатуры.', reply_markup=markup)
    received_msg[0] = 'wait'
    game()


@bot.message_handler(commands=['finish'])
def get_finish(message):
    received_msg[0] = 'status'
    received_msg[1] = 'text'
    bot.send_message(message.chat.id, 'Игра закончена. Буду рад сыграть с Вами снова! :)')
    received_msg[2] = 'chat.id'


@bot.message_handler(content_types=['text'])
def read_answer(message):
    if received_msg[0] == 'wait':
        received_msg[1] = message.text.strip()
        received_msg[0] = 'received'
    else:
        bot.send_message(message.chat.id, "Я не понял :(\nСкорее всего, это сообщение лишнее.\n\nЕсть команда /start для начала новой игры и / finish для досрочного окончания игры.\n\nОбратите внимание, что после прочтения текста вопроса нужно запустить таймер, нажав на кнопку под моим сообщением с текстом вопроса. Только после этого я смогу принять Ваш ответ.".replace('/ f', '/f'))


def inline_keyboard_msg(button_text, msg_text):
    keyboard = telebot.types.InlineKeyboardMarkup()
    if button_text in ['Следующий вопрос', 'Далее']:
        keyboard.add(telebot.types.InlineKeyboardButton(button_text, callback_data="next_question"))
    elif button_text == 'Запустить таймер':
        keyboard.add(telebot.types.InlineKeyboardButton(button_text, callback_data="start_timer"))
    bot.send_message(received_msg[2].chat.id, msg_text, reply_markup=keyboard)


@bot.callback_query_handler(lambda call: call.data in ["next_question", "start_timer"])
def handle_callback(call: telebot.types.CallbackQuery):
    if call.data == "next_question":
        received_msg[0] = 'next_question'
    elif call.data == "start_timer":
        received_msg[0] = 'start_timer'
    bot.answer_callback_query(callback_query_id=call.id)


def game():
    # Выбор количества вопросов в игре
    while True:
        if received_msg[0] == 'received':
            try:
                amount = int(received_msg[1])
            except Exception:
                bot.send_message(received_msg[2].chat.id, 'Я не понял :(\nПожалуйста, нажмите на нужную кнопку или введите целое число.')
                received_msg[0] = 'wait'
                time.sleep(0.25)
                continue
            break
        else:
            time.sleep(0.25)
    
    # Выбор сложности пакета вопросов для игры
    complexity_options = ['Любой', 'Очень простой', 'Простой', 'Средний', 'Сложный', 'Очень сложный']
    
    markup=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, row_width=2)
    markup.add(*complexity_options)
    
    bot.send_message(received_msg[2].chat.id, 'Выберите, пожалуйста, желаемую сложность пакета вопросов, нажав на нужную кнопку.', reply_markup=markup)
    received_msg[0] = 'wait'
    
    while True:
        if received_msg[0] == 'received' and received_msg[1] in complexity_options:
            complexity = f'complexity{complexity_options.index(received_msg[1])}'
            bot.send_message(received_msg[2].chat.id, f'Итак, играем {received_msg[1].lower()} пакет.\nКоличество вопросов: {amount}\nУдачи! :)', reply_markup=telebot.types.ReplyKeyboardRemove())
            break
        elif received_msg[0] == 'received':
            bot.send_message(received_msg[2].chat.id, 'Я не понял :(\nПожалуйста, выберите желаемую сложность пакета вопросов с помощью кнопок.')
            received_msg[0] = 'wait'
            time.sleep(0.25)
        else:
            time.sleep(0.25)

    # Получение вопросов с сайта базы вопросов
    web_page = get_page(amount, complexity)
    question_data = parse_questions(web_page)

    for i in range(amount):
        # Номер вопроса
        bot.send_message(received_msg[2].chat.id, f'Вопрос №{i + 1}')
        
        # Текстовая раздатка
        if question_data[1][i]:
            bot.send_message(received_msg[2].chat.id, question_data[1][i])
        
        # Раздатка (картинка)
        comment_illustr = False
        if question_data[2][i]:
            if isinstance(question_data[2][i], str):
                bot.send_photo(received_msg[2].chat.id, requests.get(question_data[2][i]).content)
            else:
                bot.send_photo(received_msg[2].chat.id, requests.get(question_data[2][i][0]).content)
                comment_illustr = True
        
        # Текст вопроса
        inline_keyboard_msg('Запустить таймер', question_data[0][i])
        while received_msg[0] != 'start_timer':
            time.sleep(0.2)

        # Ответ пользователя на вопрос
        received_msg[0] = 'wait'
        timer = 70
        bot.send_message(received_msg[2].chat.id, 'Время пошло!')
        while True:
            if received_msg[0] == 'received' and timer >= 0:
                bot.send_message(received_msg[2].chat.id, f'Ответ "{received_msg[1]}" принят.')
                break
            elif timer == 10:
                bot.send_message(received_msg[2].chat.id, 'Осталось 10 секунд.\nПора сдавать ответ!')
                timer -= 1
                time.sleep(1)
            elif timer >= 0:
                timer -= 1
                time.sleep(1)
            else:
                received_msg[0] = 'not_received'
                bot.send_message(received_msg[2].chat.id, 'Время вышло :(')
                break
        
        # Раздатка (картинка) для комментария
        if comment_illustr:
            bot.send_photo(received_msg[2].chat.id, requests.get(question_data[2][i][1]).content)
        
        # Ответ, зачёт, комментарий
        if i < amount - 1:
            inline_keyboard_msg('Следующий вопрос', question_data[3][i])
        else:
            inline_keyboard_msg('Далее', question_data[3][i])
        while received_msg[0] != 'next_question':
            time.sleep(0.2)

    received_msg[0] = 'status'
    received_msg[1] = 'text'
    bot.send_message(received_msg[2].chat.id, 'Игра окончена. Буду рад сыграть с Вами снова! :)')
    

if __name__ == '__main__':
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception:
            continue
