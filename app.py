# -*- coding: utf-8 -*-

#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

import os
import sys
from argparse import ArgumentParser
from pythainlp import word_tokenize
from keras.models import model_from_json
import pickle
import pymysql
import datetime
import json

# Connect to the database
connection = pymysql.connect(host='sql12.freemysqlhosting.net',
                             user='sql12235366',                                                   
                             password='49VyS4LHJS',
                             database='sql12235366')

from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
# kuy
app = Flask(__name__)

# get channel_secret and channel_access_token from your environment variable
channel_secret = 'c4b455f1d8e88c5de6983e43265adf0b'
channel_access_token = 'OMpCqFAGvSDFd9t6ASr8it5mcczoFaYP0kzN1aYlleVG+3phImUopXeqF68SeYXcpWLOn1XsRdkdAG5WCIuV3SUA08d7hd2KnVpYI5STDy2rexGzkvvAVJsAUjsu4gG+KvgUPaF73i5r6LRlyqlbCAdB04t89/1O/w1cDnyilFU='
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

with open('intent_arch.json') as json_data:
    intent_arch = json.load(json_data)
    print(d)
intent =  model_from_json(intent_arch)
intent.load_weights('intent_weights.h5')
with ('dictionary.pickle','rb') as f:
        dictionary = pickle.load(f)

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

def to_index(sen):
    ret = []
    for word in sen:
        try:
            ret.append(dictionary[word])
        except KeyError:
            ret.append(dictionary['UNK'])
    return ret

def get_intention(sentence):
    data = word_tokenize(sentence)
    data = to_index(data)
    while len(data)<49:
        data.append(0)
    intention = intent.predict(data)
    intention = intention.index(max(intention))
    return intention


@handler.add(MessageEvent, message=TextMessage)
def message_text(event):  
    intent = get_intention(event.message.text)
    print(intent)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=(event.message.text+str(intention)))
    )


if __name__ == "__main__":
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-p', '--port', default=8000, help='port')
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    app.run(debug=options.debug, port=options.port)
