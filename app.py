#載入LineBot所需要的模組
from email import message
from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction

app = Flask(__name__)

import os, sys
from dotenv import load_dotenv

load_dotenv()

channel_secret = os.getenv('CHANNEL_SECRET', None)
channel_access_token = os.getenv('CHANNEL_ACCESS_TOKEN', None)
uid = os.getenv('UID', None)

if channel_secret is None:
    print('Specify CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)
if uid is None:
    print('Specify UID as environment variable.')
    sys.exit(1)

# Channel Access Token
line_bot_api = LineBotApi(channel_access_token)
# Channel Secret
handler = WebhookHandler(channel_secret)


start_message = TextSendMessage(text='Do you want to start the automatically trading now?',
                               quick_reply=QuickReply(items=[
                                   QuickReplyButton(action=MessageAction(label="Sure!", text="start")),
                                   QuickReplyButton(action=MessageAction(label="Wait a minute...", text="wait"))
                               ]))
# quick reply message
line_bot_api.push_message(uid, start_message)

# 監聽所有來自 /callback 的 Post Request
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
        api_key = key_val.split(':')[1]
        api_secret = secret_val.split(':')[1]
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
    elif "api_key" in event.message.text and "api_secret" in event.message.text:
        reply = event.message.text
        symbol_val, lookback_period_val, change_in_price_val, stop_loss_val, take_profit_val, qty_val = reply.split('\n')
        SYMBOL = symbol_val.split(':')[1]
        LOOKBACK_PERIOD = lookback_period_val.split(':')[1]
        CHANGE_IN_PRICE = change_in_price_val.split(':')[1]
        STOP_LOSS = stop_loss_val.split(':')[1]
        TAKE_PROFIT = take_profit_val.split(':')[1]
        QTY = qty_val.split(':')[1]
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
    app.run()