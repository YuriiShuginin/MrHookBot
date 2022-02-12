import config
import requests
import telebot
from bs4 import BeautifulSoup
import re
import time


bot = telebot.TeleBot(config.access_token)


def get_page() -> str:
    url = f'{config.domain}/random/types1'
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


@bot.message_handler(commands=['start'])
def get_start(message):
    bot.send_message(message.chat.id, 'Привет! Я умею задавать вопросы из базы спортивного "Что? Где? Когда?". Сыграем!')
    web_page = get_page()
    question_data = parse_questions(web_page)

    for i in range(24):
        bot.send_message(message.chat.id, f'Вопрос №{i + 1}')
        
        if question_data[1][i]:
            bot.send_message(message.chat.id, question_data[1][i])
        
        comment_illustr = False
        if question_data[2][i]:
            if isinstance(question_data[2][i], str):
                bot.send_photo(message.chat.id, requests.get(question_data[2][i]).content)
            else:
                bot.send_photo(message.chat.id, requests.get(question_data[2][i][0]).content)
                comment_illustr = True
        
        bot.send_message(message.chat.id, question_data[0][i])

        bot.send_message(message.chat.id, question_data[3][i])
        
        if comment_illustr:
            bot.send_photo(message.chat.id, requests.get(question_data[2][i][1]).content)
        
        if i % 20 == 0 and i != 0:
            time.sleep(11)
    
    bot.send_message(message.chat.id, 'Игра окончена. Буду рад сыграть с Вами снова! :)')


@bot.message_handler(commands=['finish'])
def get_finish(message):
    bot.send_message(message.chat.id, 'Игра закончена досрочно. Буду рад сыграть с Вами снова! :)')


if __name__ == '__main__':
    bot.polling(none_stop=True)
