import configparser
import logging

import telebot
from peewee import IntegerField, IntegrityError, Model, SqliteDatabase

import os
from flask import Flask, request

app = Flask(__name__)

config = configparser.ConfigParser()
config.read("config.ini")
parsed_types = config.get("Tech", "forward-types").split(";")
logging.basicConfig(format=config.get("Tech", "logger-format"))

support_chat_id = os.getenv("support_chat_id")
TOKEN = "6431884643:AAGZ4LVh8ZK7fNFS2o-QMJzKMZyBspF3uSw" #str(os.getenv("token"))
bot = telebot.TeleBot(TOKEN)

db = SqliteDatabase("db.sqlite3")

if config.getboolean("Tech", "proxy"):
    telebot.apihelper.proxy = {"https": config.get("Tech", "proxy-server")}


class Block(Model):
    user_id = IntegerField(unique=True)

    class Meta:
        database = db


class Message(Model):
    from_ = IntegerField()
    id = IntegerField(unique=True)

    class Meta:
        database = db


db.create_tables([Block, Message])


# class Filters:
def is_user(message):
    return (
        message.chat.id != support_chat_id
        and message.chat.type == "private"
    )


def is_admin(message):
    return message.chat.id == support_chat_id


def is_answer(message):
    return (
        message.chat.id == support_chat_id
        and message.reply_to_message is not None
        and message.reply_to_message.forward_date is not None
    )


def is_blocked(message):
    return Block.select().where(Block.user_id == message.chat.id).exists()


def is_not_blocked(message):
    return not Block.select().where(Block.user_id == message.chat.id).exists()


@bot.message_handler(commands=["start"])
def send_start(message):
    bot.send_message(message.chat.id, config.get("Messages", "start"))


@bot.message_handler(commands=["help"])
def send_help(message):
    bot.send_message(message.chat.id, config.get("Messages", "help"))


@bot.message_handler(
    content_types=parsed_types,
    func=lambda msg: is_user(msg) and is_not_blocked(msg),
)
def get_question(message):
    if config.getboolean("Tech", "success-question-message"):
        bot.send_message(message.chat.id, config.get("Messages", "question-was-sent"))
    sent = bot.forward_message(
        support_chat_id, message.chat.id, message.message_id
    )
    Message.create(from_=message.chat.id, id=sent.message_id).save()


@bot.message_handler(func=is_user)
def get_error_question(message):
    bot.send_message(message.chat.id, config.get("Messages", "question-wasnt-sent"))


@bot.message_handler(commands=["block"], func=is_answer)
def block(message):
    user_id = (
        Message.select()
        .where(Message.id == message.reply_to_message.message_id)
        .get()
        .from_
    )
    try:
        Block.create(user_id=user_id).save()
    except IntegrityError:
        pass

    bot.send_message(
        message.chat.id, config.get("Messages", "block-user").format(user_id=user_id)
    )


@bot.message_handler(commands=["unblock"], func=is_answer)
def unblock(message):
    user_id = (
        Message.select()
        .where(Message.id == message.reply_to_message.message_id)
        .get()
        .from_
    )
    try:
        Block.select().where(Block.user_id == user_id).get().delete_instance()
    except Block.DoesNotExist:
        pass

    bot.send_message(
        message.chat.id, config.get("Messages", "unblock-user").format(user_id=user_id)
    )


@bot.message_handler(content_types=["text", "photo"], func=is_answer)
def answer_question(message):
    to_user_id = (
        Message.select()
        .where(Message.id == message.reply_to_message.message_id)
        .get()
        .from_
    )
    if message.photo is not None:
        bot.send_photo(
            to_user_id,
            message.photo[-1].file_id,
            message.caption,
        )
    else:
        bot.send_message(
            to_user_id,
            config.get("Messages", "get-answer").format(message=message.text),
        )
    if config.getboolean("Tech", "success-answer-message"):
        bot.send_message(
            message.chat.id,
            config.get("Messages", "answer-was-sent"),
            reply_to_message_id=message.message_id,
        )


# def main():
#     bot.delete_webhook()
#     bot.infinity_polling(none_stop=True, timeout=60)


@app.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200


@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=config.get("Tech", "url") + TOKEN)
    return "!", 200


if __name__ == "__main__":
    app.run(threaded=True, host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
    # main()
