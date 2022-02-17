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
        answers[i] = " ".join(ans[0].find_parent("p").text.split()).replace('Ответ:', '<strong>Ответ:</strong>')
    
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
            answers[i] += "\n" + " ".join(alter_answers[0].find_parent("p").text.split()).replace('Зачёт:', '<strong>Зачёт:</strong>')

        comment = None # Данные об авторских комментариях к ответам
        comment = questions_info[i].find_all(string=re.compile("Комментарий"))
        if comment:
            answers[i] += "\n\n" + " ".join(comment[0].find_parent("p").text.split()).replace('Комментарий:', '<strong>Комментарий:</strong>')

    return question_texts, handouts, illustrations, answers


received_msg = {}


@bot.message_handler(commands=['start'])
def get_start(message):
    received_msg[message.chat.id] = ['status', 'text', 'chat.id']
    received_msg[message.chat.id][2] = message.chat.id
    amount_options = ['12', '24', '36', '45', '60', '90']
    markup=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, row_width=3)
    markup.add(*amount_options)
    bot.send_message(message.chat.id, 'Привет! Я умею задавать вопросы из базы спортивного "Что? Где? Когда?".\n\nСколько вопросов Вы хотите отыграть?\n\nВы можете выбрать один из предложенных вариантов, нажав на кнопку, или ввести любое число с помощью клавиатуры.', reply_markup=markup)
    received_msg[message.chat.id][0] = 'wait'
    game(message.chat.id)


@bot.message_handler(commands=['finish'])
def get_finish(message):
    received_msg[message.chat.id][0] = 'finish'
    received_msg[message.chat.id][1] = 'text'
    bot.send_message(message.chat.id, 'Игра закончена. Буду рад сыграть с Вами снова! :)')
    received_msg[message.chat.id][2] = 'chat.id'


@bot.message_handler(content_types=['text'])
def read_answer(message):
    if received_msg[message.chat.id][0] == 'wait':
        received_msg[message.chat.id][1] = message.text.strip()
        received_msg[message.chat.id][0] = 'received'
    else:
        bot.send_message(message.chat.id, "Я не понял :(\nСкорее всего, это сообщение лишнее.\n\nЕсть команда /start для начала новой игры и / finish для досрочного окончания игры.\n\nОбратите внимание, что после прочтения текста вопроса нужно запустить таймер, нажав на кнопку под моим сообщением с текстом вопроса. Только после этого я смогу принять Ваш ответ.".replace('/ f', '/f'))


def inline_keyboard_msg(button_text, msg_text, chat_id):
    keyboard = telebot.types.InlineKeyboardMarkup()
    if button_text in ['Следующий вопрос', 'Далее']:
        keyboard.add(telebot.types.InlineKeyboardButton(button_text, callback_data="next_question"))
        received_msg[chat_id][0] = 'wait_next_callback'
    elif button_text == 'Запустить таймер':
        keyboard.add(telebot.types.InlineKeyboardButton(button_text, callback_data="start_timer"))
        received_msg[chat_id][0] = 'wait_start_callback'
    bot.send_message(chat_id, msg_text, reply_markup=keyboard, parse_mode='HTML')


@bot.callback_query_handler(lambda call: call.data in ["next_question", "start_timer"])
def handle_callback(call: telebot.types.CallbackQuery):
    if call.data == "next_question" and received_msg[call.message.chat.id][0] == 'wait_next_callback':
        received_msg[call.message.chat.id][0] = 'next_question'
    elif call.data == "start_timer" and received_msg[call.message.chat.id][0] == 'wait_start_callback':
        received_msg[call.message.chat.id][0] = 'start_timer'
    bot.answer_callback_query(callback_query_id=call.id)


def game(chat_id):
    # Выбор количества вопросов в игре
    while True:
        if received_msg[chat_id][0] == 'received':
            try:
                amount = int(received_msg[chat_id][1])
            except Exception:
                bot.send_message(chat_id, 'Я не понял :(\nПожалуйста, нажмите на нужную кнопку или введите целое число.')
                received_msg[chat_id][0] = 'wait'
                time.sleep(0.25)
                continue
            break
        elif received_msg[chat_id][0] == 'finish':
            return None
        else:
            time.sleep(0.25)
    
    # Выбор сложности пакета вопросов для игры
    complexity_options = ['Любой', 'Очень простой', 'Простой', 'Средний', 'Сложный', 'Очень сложный']
    
    markup=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, row_width=2)
    markup.add(*complexity_options)
    
    bot.send_message(chat_id, 'Выберите, пожалуйста, желаемую сложность пакета вопросов, нажав на нужную кнопку.', reply_markup=markup)
    received_msg[chat_id][0] = 'wait'
    
    while True:
        if received_msg[chat_id][0] == 'received' and received_msg[chat_id][1] in complexity_options:
            complexity = f'complexity{complexity_options.index(received_msg[chat_id][1])}'
            bot.send_message(chat_id, f'Итак, играем {received_msg[chat_id][1].lower()} пакет.\nКоличество вопросов: {amount}\nУдачи! :)', reply_markup=telebot.types.ReplyKeyboardRemove())
            break
        elif received_msg[chat_id][0] == 'received':
            bot.send_message(chat_id, 'Я не понял :(\nПожалуйста, выберите желаемую сложность пакета вопросов с помощью кнопок.')
            received_msg[chat_id][0] = 'wait'
            time.sleep(0.25)
        elif received_msg[chat_id][0] == 'finish':
            return None
        else:
            time.sleep(0.25)

    # Получение вопросов с сайта базы вопросов
    web_page = get_page(amount, complexity)
    question_data = parse_questions(web_page)

    result = 0
    for i in range(amount):
        # Номер вопроса
        bot.send_message(chat_id, f'<strong>Вопрос №{i + 1}</strong>', parse_mode='HTML', reply_markup=telebot.types.ReplyKeyboardRemove())
        
        # Текстовая раздатка
        if question_data[1][i]:
            bot.send_message(chat_id, question_data[1][i])
        
        # Раздатка (картинка)
        comment_illustr = False
        if question_data[2][i]:
            if isinstance(question_data[2][i], str):
                bot.send_photo(chat_id, requests.get(question_data[2][i]).content)
            else:
                bot.send_photo(chat_id, requests.get(question_data[2][i][0]).content)
                comment_illustr = True
        
        # Текст вопроса
        inline_keyboard_msg('Запустить таймер', question_data[0][i], chat_id)
        while received_msg[chat_id][0] != 'start_timer':
            if received_msg[chat_id][0] == 'finish':
                return None
            time.sleep(0.2)
        
        # Ответ пользователя на вопрос
        received_msg[chat_id][0] = 'wait'
        timer = 70
        bot.send_message(chat_id, 'Время пошло!')
        while True:
            if received_msg[chat_id][0] == 'received' and timer >= 0:
                user_answer = received_msg[chat_id][1]
                bot.send_message(chat_id, f'Ответ "{user_answer}" принят.')
                break
            elif received_msg[chat_id][0] == 'finish':
                return None
            elif timer == 10:
                bot.send_message(chat_id, 'Осталось 10 секунд.\nПора сдавать ответ!')
                timer -= 1
                time.sleep(1)
            elif timer >= 0:
                timer -= 1
                time.sleep(1)
            else:
                received_msg[chat_id][0] = 'not_received'
                user_answer = ''
                bot.send_message(chat_id, 'Время вышло :(')
                break
        
        # Раздатка (картинка) для комментария
        if comment_illustr:
            bot.send_photo(chat_id, requests.get(question_data[2][i][1]).content)
        
        # Ответ, зачёт, комментарий
        bot.send_message(chat_id, question_data[3][i], parse_mode='HTML')
        
        # Засчитывание ответа
        if user_answer:
            correct_options = ['Да', 'Нет']
            markup=telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, row_width=2)
            markup.add(*correct_options)
            bot.send_message(chat_id, f'Ваш ответ "{user_answer}" попадает в зачёт?', reply_markup=markup)
            
            received_msg[chat_id][0] = 'wait'
            while True:
                if received_msg[chat_id][0] == 'received' and received_msg[chat_id][1] in correct_options:
                    if received_msg[chat_id][1] == 'Да':
                        result += 1
                    break
                elif received_msg[chat_id][0] == 'received':
                    bot.send_message(chat_id, 'Я не понял :(\nПожалуйста, ответьте на мой вопрос с помощью кнопок или клавиатуры (Да / Нет)')
                    received_msg[chat_id][0] = 'wait'
                    time.sleep(0.25)
                elif received_msg[chat_id][0] == 'finish':
                    return None
                else:
                    time.sleep(0.25)
        
        if i < amount - 1:
            inline_keyboard_msg('Следующий вопрос', f'Текущий результат: {result} из {i + 1}', chat_id)
        else:
            inline_keyboard_msg('Далее', f'Текущий результат: {result} из {i + 1}', chat_id)
        while True:
            if received_msg[chat_id][0] == 'next_question':
                break
            elif received_msg[chat_id][0] == 'finish':
                return None
            else:
                time.sleep(0.2)
    
    received_msg[chat_id][0] = 'status'
    received_msg[chat_id][1] = 'text'
    bot.send_message(chat_id, f'Игра окончена.\n\nИтоговый результат: {result} из {amount}\n\nБуду рад сыграть с Вами снова! :)', reply_markup=telebot.types.ReplyKeyboardRemove())
    

if __name__ == '__main__':
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception:
            continue
