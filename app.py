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
import numpy as np
import pandas as pd
import redis
import re


def clean_sentence(s):
    s = s.lower()
    if re.search(r'[bB]ot\s*:*',s):
        return ''
    s = re.sub(r'</*[a-zA-Z_]*>', '', s)
    s = re.sub(r'[0-9]*\.', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()
def get_label(s):
    label = re.findall(r'<[A-Z_]*>',s)
    if label:
        return label[0]
    else:
        return '<NONE>'
def clean_sentence_for_tagging(s):
    s = s
    if re.search(r'[bB]ot\s*:*',s):
        return ''
    s = re.sub(r'[0-9]*\.', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()
def clean_color(s):
    s = s.lower()
    s = re.sub(r'สี','',s)
    s = re.sub(r'\s+', ' ', s)
    clean_dict = {'ขา':'ขาว',
                 'เท่า':'เทา'}
    if s in clean_dict:
        s = clean_dict[s]
    return s.strip()
def clean_brand(s):
    s = s.lower()
    s = re.sub(r'\s+', ' ', s)
    return s.strip()
def clean_model(s):
    s = s.strip().lower()
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'iphone', '', s)
    s = re.sub(r'[0-9]*\s*gb', '', s)
    return s.strip()

r = redis.StrictRedis(host='redis-19121.c1.ap-southeast-1-1.ec2.cloud.redislabs.com',port=19121,password='NLPchatbotProject',decode_responses=True,db=0)

# Connect to the database
# connection = pymysql.connect(host='sql12.freemysqlhosting.net',
#                              user='sql12235366',                                                   
#                              password='49VyS4LHJS',
#                              database='sql12235366')

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
    intent_arch = json_data.read()
intent =  model_from_json(intent_arch)
intent.load_weights('model_weights.h5')
dictionary = pickle.load(open('dictionary.pickle','rb'))
brand_dict_map = {'iphone':'apple','ไอโฟน':'apple','galaxy':'samsung'}

mobile_df = pd.read_csv('mobile.csv',names=['brand','model','price','color','capacity','description'])
mobile_df.color = mobile_df.color.apply(lambda k: ':'.join([clean_color(s) for s in k.split(':')]))
mobile_df.model = mobile_df.model.apply(lambda k: clean_model(k))
mobile_df.head()
mobile_df.describe(include='all')

color_dict = np.load('./color_dict.npy')
color_dict = np.vectorize(lambda k: ':'.join([clean_color(s) for s in k.split(':')]))(color_dict)
color_dict = np.unique(color_dict)

brand_dict = np.load('./brand_dict.npy')

model_dict = np.load('./model_dict.npy')
model_dict = np.vectorize(clean_model)(model_dict)
model_dict = np.unique(model_dict)

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
    data = data[:49] + [0]*(49 - len(data))
    data = np.array([data])
    intention = intent.predict(data)
    # print(intention)
    intention = intention[0].argmax()
    # print(intention)
    return intention

def predict_tag(sen, debug=True):
    item={}
    current_brand = ''
    current_model = ''
    current_color = ''
    current_capacity = ''
    current_desc = ''
    if debug:
        print('sen:',sen)
    for brand in brand_dict:
        if sen.find(brand) != -1:
            if debug:
                print('brand = ',brand)
            current_brand = brand
            item['brand'] = brand
            break
    if current_brand == '':
        for brand,mapped_brand in brand_dict_map.items():
            if sen.find(brand) != -1:
                if debug:
                    print('brand = ',mapped_brand)
                current_brand = mapped_brand
                item['brand'] = mapped_brand
                break
    if current_brand == '':
        if debug:
            print('no brand')
#         break
    for model in model_dict:
        if sen.lower().find(model) != -1:
            if debug:
                print('model = ',model)
            current_model = model
            item['model'] = model
            break
    if current_model == '':
        if debug:
            print('no model')
#         break
    for color in color_dict:
        if sen.lower().find(color) != -1:
            if debug:
                print('color = ',color)
            current_color = color
            item['color'] = color
            break
    if current_color == '':
        if debug:
            print('no color')
#         break
    for capa in [8,16,32,64,128,256,512]:
        if re.search(r'{}\s*[Gg][Bb]'.format(capa),sen):
            current_capacity = capa
            item['capa'] = capa
    if current_brand !='' and current_model != '':
        # not sure should use head or not??
        # but do i need this?
        current_desc = mobile_df[(mobile_df['brand'] == current_brand) & (mobile_df['model']==current_model)].head(1)
        if debug:
            print('desciption:\n',current_desc['description'])
    print(item)
    return item

"""
DB (session_id,brand,model,capa,color,address)
"""
def escape_name(s):
    """Escape name to avoid SQL injection and keyword clashes.

    Doubles embedded backticks, surrounds the whole in backticks.

    Note: not security hardened, caveat emptor.

    """
    return '`{}`'.format(s.replace('`', '``'))

def get_user(userid):
    item = r.hgetall(userid)
    print(userid,item)
    if not item:
        item = {}
    return item

# def get_user(userid):
#     cursor = connection.cursor()
#     sql = "SELECT * FROM chatbot WHERE `session_id`=%s"
#     cursor.execute(sql, (userid))
#     result = cursor.fetchone()
#     print("queried",result)
#     # names = list(items)
#     # cols = ', '.join(map(escape_name, names))
#     if not result:
#         sql = "INSERT INTO chatbot (`session_id`) VALUES (%s)"
#         cursor.execute(sql, (userid))
#         connection.commit()
#         result = (userid,'','','','','')
#     #     query = "INSERT IGNORE INTO chatbot (session_id, ,brand,model,capa,color,price) VALUES (%s, %s,%s, %s,%s)"
#     #     cursor.execute(query, items)
#     # else:
#     #     ss = zip(cols, list(items.values())
#     #     query = 'UPDATE chatbot SET session_id =%s,brand = %s,model = %s,capa=%s,color=%s,price=%s WHERE `session_id`=%s'.format(ss[0],ss[1],userid)
#     #     cursor.execute(query, items)
#     # query = "INSERT IGNORE INTO chatbot (session_id, ,brand,model,capa,color,price) VALUES (%s, %s,%s, %s,%s)"
#     # cursor.execute(query, items)
#     return result

def insert_things(userid,items):
    r.delete(userid)
    if r.hmset(userid,items):
        print("inserted")
    # cursor = connection.cursor()
    # query = "REPLACE INTO chatbot (session_id,brand,model,capa,color,price) VALUES (%s, %s,%s, %s,%s,%s)"
    # cursor.execute(query, items)
    # connection.commit()
    

intent_dict ={0: '<PRICE>', 1: '<INFO>', 2: '<NONE>', 3: '<BUY>'}

def get_ans(message,intent,userid):
    # tokens = word_tokenize(message)
    print("getting ans")
    prediction = intent_dict[intent]
    print("got intent:",prediction)
    item = get_user(userid)
    if prediction == '<NONE>':
        try:
            prediction = item['intent']
        except KeyError:# set price as default intent
            prediction = '<PRICE>'
    print("using intent:",prediction)
    print("got user")
    # current_brand,current_model,current_color,current_capacity,current_desc = predict_tag(message,debug=True)
    pred_item = predict_tag(message,debug=True)
    print(pred_item)
    # if current_brand != brand and current_brand:
    #     items = ('brand':current_brand,'model':current_model,'color':current_color,'capa':current_capacity,'address':current_desc)
    # else:
    #     if current_model != model and not model:
    #         current_model = model
    #     if current_color != color and not color:
    #         current_color = color
    #     if current_capacity != capa and not capa:
    #         curent_capacity = capa
    #     if current_desc != address and not address:
    #         current_desc = address
    #      items = ('brand':current_brand,'model':current_model,'color':current_color,'capa':current_capacity,'address':current_desc)
    for w in pred_item:
        print(w)
        if w == 'brand':
            item = pred_item
        else:
            item[w] = pred_item[w]
    item['intent'] = prediction
    print("item:",item)
    insert_things(userid,item)
    answer = ''
    if 'brand' not in item:
        answer = 'กรุณาระบุยี่ห้อด้วยครับ'
    elif 'model' not in item:
        answer = 'กรุณาระบุรุ่นด้วยครับ'
    elif prediction == '<PRICE>':
        if item['brand'] == 'apple':
            if 'capa' not in item:
                answer = 'กรุณาระบุขนาดความจุด้วยครับ'
            else:
                description = mobile_df[(mobile_df.brand=='apple')&
                                   (mobile_df.model==current_model)&
                                   (mobile_df.capacity==current_capacity)]['price'].values
                if description:
                    answer = description
                else:
                    answer = """ไม่พบข้อมูลโทรศัพท์
                                brand: {}
                                model: {}
                                capacity: {}""".format(item['brand'],
                                                    item['model'],
                                                    item['capa'])
        else:
            description = mobile_df[(mobile_df.brand==current_brand)&
                               (mobile_df.model==current_model)]['price'].values
            if description:
                answer = description
            else:
                answer = """ไม่พบข้อมูลโทรศัพท์
                            brand: {}
                            model: {}""".format(item['brand'],
                                                item['model'])
    elif prediction == '<INFO>':
        if item['brand'] == 'apple':
            if 'capa' not in item:
                answer = 'กรุณาระบุขนาดความจุด้วยครับ'
            else:
                description = mobile_df[(mobile_df.brand=='apple')&
                                   (mobile_df.model==current_model)&
                                   (mobile_df.capacity==current_capacity)]['description'].values
                if description:
                    answer = description
                else:
                    answer = """ไม่พบข้อมูลโทรศัพท์
                                brand: {}
                                model: {}
                                capacity: {}""".format(item['brand'],
                                                    item['model'],
                                                    item['capa'])
        else:
            description = mobile_df[(mobile_df.brand==current_brand)&
                               (mobile_df.model==current_model)]['description'].values
            if description:
                answer = description
            else:
                answer = """ไม่พบข้อมูลโทรศัพท์
                            brand: {}
                            model: {}""".format(item['brand'],
                                                item['model'])
    elif prediction == '<BUY>':
        if 'color' not in item:
            answer = 'กรุณาระบุสีที่ต้องการด้วยครับ'
        elif item['brand'] == 'apple':
            if 'capa' not in item:
                answer = 'กรุณาระบุขนาดความจุด้วยครับ'
            else:
                answer = """กรุณายืนยันการสั่งสินค้าด้วยครับ
                            brand: {}
                            model: {}
                            color: {}
                            capacity: {}""".format(item['brand'],
                                                  item['model'],
                                                  item['color'],
                                                  item['capa'])
        else:
            answer = """กรุณายืนยันการสั่งสินค้าด้วยครับ
                        brand: {}
                        model: {}
                        color: {}""".format(item['brand'],
                                            item['model'],
                                            item['color'])
    print('ans:',answer)
    return answer

@handler.add(MessageEvent, message=TextMessage)
def message_text(event):
    message = event.message.text
    userid = event.source.user_id
    # print(message)
    intention = get_intention(message)
    ans=get_ans(message,intention,userid)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=(ans))
    )


if __name__ == "__main__":
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-p', '--port', default=8000, help='port')
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    app.run(debug=options.debug, port=options.port)
