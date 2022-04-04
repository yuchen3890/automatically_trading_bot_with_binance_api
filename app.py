# packages for linebot
from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, 
    TextMessage, 
    TextSendMessage, 
    QuickReply, 
    QuickReplyButton, 
    MessageAction
)

# packages for trading
import pandas as pd
from binance.client import Client

import requests
from datetime import datetime

app = Flask(__name__)

import os, sys
from dotenv import load_dotenv

load_dotenv()

## get env parameters 
channel_secret = os.getenv('CHANNEL_SECRET', None)
channel_access_token = os.getenv('CHANNEL_ACCESS_TOKEN', None)
uid = os.getenv('USER_ID', None)

if channel_secret is None:
    print('Specify CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)
if uid is None:
    print('Specify UID as environment variable.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

start_message = TextSendMessage(text='Do you want to start the automatically trading now?',
                               quick_reply=QuickReply(items=[
                                   QuickReplyButton(action=MessageAction(label="Sure!", text="start")),
                                   QuickReplyButton(action=MessageAction(label="Wait a minute...", text="wait"))
                               ]))
# quick reply message
line_bot_api.push_message(uid, start_message)

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
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

#### automatically trading
## global variables initialization
api_key = None
api_secret = None
SYMBOL = None
LOOKBACK_PERIOD = 0
CHANGE_IN_PRICE = 0.0
STOP_LOSS = 0.0
TAKE_PROFIT = 0.0
QTY = 0.0
df_current = pd.DataFrame()
open_position = False

def init_client():
    client = Client(api_key, api_secret, testnet=True)
    return client

def createDataFrame(data):
    df = pd.DataFrame([data])
    df = df.loc[:, ['symbol', 'price']]
    df['time'] = datetime.now()
    df.price = df.price.astype(float)
    return df

def automatic_trading(client):
    line_bot_api.push_message(uid, TextSendMessage(text="Start trading for you!"))
    cnt = 0
    while True:
        cnt += 1
        print(cnt, end="\r")
        # binance api url
        key = f"https://api.binance.com/api/v3/ticker/price?symbol={SYMBOL}" 
        # requesting data from url
        data = requests.get(key)  
        data = data.json()
        global df_current
        df_current = df_current.append(createDataFrame(data), ignore_index=True)

        lookbackperiod = df_current.iloc[-LOOKBACK_PERIOD:]
        # pct_change: percentage change(compare with the row above)
        # cumprod: cumulative production
        rising_pct = (lookbackperiod.price.pct_change() + 1).cumprod() - 1
        global open_position
        if not open_position:
            if rising_pct.last_valid_index() != None:
                if rising_pct[rising_pct.last_valid_index()] > CHANGE_IN_PRICE:
                    line_bot_api.push_message(uid, TextSendMessage(text="Start placing buying order."))
                    buying_order = client.create_order(symbol=SYMBOL,
                                        side='BUY',
                                        type='MARKET',
                                        quantity= QTY)
                    line_bot_api.push_message(uid, TextSendMessage(text="Finish placing buying order. \
                        Here's the information of the buying order:"))

                    trans_time =  pd.to_datetime(buying_order['transactTime'], unit='ms')
                    line_bot_api.push_message(uid, TextSendMessage(text=f"Transaction time:{trans_time}"))

                    for item in buying_order['fills']:
                        line_bot_api.push_message(uid, TextSendMessage(text=f"Trade id: {item['tradeId']}, \
                            Price: {item['price']}, \
                            Quantity: {item['qty']} \
                            "))
                    open_position = True
                    break
    cnt = 0
    if open_position:
        while True:
            cnt += 1
            print(cnt, end="\r")
            key = f"https://api.binance.com/api/v3/ticker/price?symbol={SYMBOL}" 
            data = requests.get(key)  
            data = data.json()

            df_current = df_current.append(createDataFrame(data), ignore_index=True)
            afterBuying = df_current.loc[df_current.time > \
                pd.to_datetime(buying_order['transactTime'], unit='ms')]
            if len(afterBuying) > 1:
                rising_pct = (afterBuying.price.pct_change() + 1).cumprod() - 1
                last_rising_pct = rising_pct[rising_pct.last_valid_index()]
                if last_rising_pct > TAKE_PROFIT or last_rising_pct < STOP_LOSS:
                    line_bot_api.push_message(uid, TextSendMessage(text="Start placing selling order."))
                    selling_order = client.create_order(symbol=SYMBOL,
                                    side='SELL',
                                    type='MARKET',
                                    quantity= QTY)
                    line_bot_api.push_message(uid, TextSendMessage(text="Finish placing selling order. \
                        Here's the information of the selling order:"))

                    trans_time =  pd.to_datetime(selling_order['transactTime'], unit='ms')
                    line_bot_api.push_message(uid, TextSendMessage(text=f"Transaction time: {trans_time}"))

                    for item in selling_order['fills']:
                        line_bot_api.push_message(uid, \
                            TextSendMessage(text=f"Trade id: {item['tradeId']}, \
                            Price: {item['price']}, \
                            Quantity: {item['qty']} \
                            "))
                    break

        ## profit/loss counting
        sum = 0
        for item in buying_order['fills']:
            sum -= float(item['price'])*float(item['qty'])
        for item in selling_order['fills']:
            sum += float(item['price'])*float(item['qty'])
        if sum >= 0:
            line_bot_api.push_message(uid, \
            TextSendMessage(text=f"Congratulations! You earn {sum} USDT in this trade!"))
        else:
            line_bot_api.push_message(uid, \
            TextSendMessage(text=f"Oops...You lose {sum} USDT this time."))

        line_bot_api.push_message(uid, \
        TextSendMessage(text="If you want to start automatically trading again, please enter 'start'."))
        return

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    if event.message.text == "wait":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="Ok, then please enter 'start' whenever you want to start trading.^^"))
    elif event.message.text == "Start" or event.message.text == "start":
        line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text="Great! First, please give me your Binance api_key & api_secret, then enter 'strategy' and we'll get moving on the next step."),
            TextSendMessage(text="Please reply in this format:\
                    api_key:    \
                    api_secret:\
                ")
            ])
    elif "api_key" in event.message.text and "api_secret" in event.message.text:
        reply = event.message.text
        key_val, secret_val = reply.split('\n')
        global api_key, api_secret
        api_key = key_val.split(':')[1].strip()
        api_secret = secret_val.split(':')[1].strip()
    elif event.message.text == "Strategy" or event.message.text == "strategy":
        line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text="OK! It's time to build up your own strategies, please read the information below and reply the settings in the specific format:"),
            TextSendMessage(text="You can get more information about these attributes just through entering its name(e.g., SYMBOL)"),
            TextSendMessage(text="Please reply in this format:\
                    SYMBOL:\
                    LOOKBACK_PERIOD:\
                    CHANGE_IN_PRICE:\
                    STOP_LOSS:\
                    TAKE_PROFIT:        \
                    QTY:\
                ")
            ])
    elif "SYMBOL" in event.message.text and \
            "LOOKBACK_PERIOD" in event.message.text and \
            "CHANGE_IN_PRICE" in event.message.text and \
            "STOP_LOSS" in event.message.text and \
            "TAKE_PROFIT" in event.message.text and \
            "QTY" in event.message.text:
        reply = event.message.text
        symbol_val, lookback_period_val, change_in_price_val, stop_loss_val, take_profit_val, qty_val = reply.split('\n')
        global SYMBOL, LOOKBACK_PERIOD, CHANGE_IN_PRICE, STOP_LOSS, TAKE_PROFIT, QTY
        SYMBOL = symbol_val.split(':')[1]
        LOOKBACK_PERIOD = int(lookback_period_val.split(':')[1])
        CHANGE_IN_PRICE = float(change_in_price_val.split(':')[1])
        STOP_LOSS = float(stop_loss_val.split(':')[1])
        TAKE_PROFIT = float(take_profit_val.split(':')[1])
        QTY = float(qty_val.split(':')[1])

        ### start trading
        client = init_client()
        automatic_trading(client)
    elif event.message.text == "SYMBOL" or event.message.text == "symbol":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="The coin pair type that you want to trade, e.g., BTCUSDT means you want to buy and sell BTC using its USDT price."))
    elif event.message.text == "LOOKBACK_PERIOD" or event.message.text == "lookback_period":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="You will have a trade based on this period."))
    elif event.message.text == "CHANGE_IN_PRICE" or event.message.text == "change_in_price":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="When the price of the coin rised more than this number in the LOOKBACK_PERIOD, I'll buy it."))
    elif event.message.text == "STOP_LOSS" or event.message.text == "stop_loss":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="After buying, if the price of the coin drop down more than this number, I'll sell it to stop loss."))
    elif event.message.text == "TAKE_PROFIT" or event.message.text == "take_profit":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="After buying, if the price of the coin rise up more than this number, I'll sell it to take profit."))
    elif event.message.text == "QTY" or event.message.text == "qty":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="Quantity that you trade in one transaction."))
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="Sorry, I'm not sure what you're saying."))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=os.getenv("PORT", 5000))