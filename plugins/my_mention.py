from slackbot.bot import respond_to
from slackbot.bot import listen_to
from slackbot.bot import default_reply

import scrapy
from twisted.internet import reactor
from scrapy.crawler import CrawlerRunner
import chardet
from multiprocessing import Process, Queue
import os
from selenium import webdriver
from slacker import Slacker

# 定数モジュール
import sys
sys.path.append("./plugins/")
import const

#################################
# グローバル変数
#################################
curpath             = (os.path.dirname(__file__))
fpath               = curpath + const.FPATH
v_info              = const.VERSION_INFO
user_info           = None
channel_info        = None
g_name              = const.NAME
g_allowed_domains   = [const.ALLOWED_DOMAINS]
g_start_urls        = [const.START_URLS]

#################################
# Spider
#################################
class TimeStampSpider(scrapy.Spider):
    '''
    出勤打刻する
    '''

    global user_info
    global g_name
    global g_allowed_domains
    global g_start_urls

    name            = g_name
    allowed_domains = g_allowed_domains
    start_urls      = g_start_urls

    custom_settings = {
            'ROBOTSTXT_OBEY':False
    }

    # ログイン画面
    def parse(self, response):

        f_data = { \
                const.FORM_NAME_02: user_info['id'], \
                const.FORM_NAME_03: user_info['pw'] \
        }
        return scrapy.FormRequest.from_response(
            response,
            formdata=f_data,
            callback=self.after_login,
            dont_filter=True
        )

    # 打刻レコーダー画面
    def after_login(self, response):

        f_data = { \
            const.FORM_NAME_11: user_info['devision'], \
            const.FORM_NAME_16: user_info['department'], \
            const.FORM_NAME_12: '1' \
        }
        return scrapy.FormRequest.from_response(
            response,
            formdata=f_data,
            callback=self.after_attend,
            dont_filter=True
        )

    # 打刻後
    def after_attend(self, response):
        post_ss(response)
 
class TimeStampFinishSpider(scrapy.Spider):
    '''
    退勤打刻する
    '''

    global user_info
    global g_name
    global g_allowed_domains
    global g_start_urls

    name            = g_name
    allowed_domains = g_allowed_domains
    start_urls      = g_start_urls

    custom_settings = {
            'ROBOTSTXT_OBEY':False
    }

    # ログイン画面
    def parse(self, response):
        f_data = { \
                const.FORM_NAME_02: user_info['id'], \
                const.FORM_NAME_03: user_info['pw'] \
        }
        return scrapy.FormRequest.from_response(
            response,
            formdata=f_data,
            callback=self.after_login,
            dont_filter=True
        )

    # 打刻レコーダー画面
    def after_login(self, response):

        f_data = { \
                const.FORM_NAME_11: user_info['devision'], \
                const.FORM_NAME_16: user_info['department'], \
                const.FORM_NAME_18: user_info['next_department'], \
                const.FORM_NAME_12: '4' \
        }
        return scrapy.FormRequest.from_response(
            response,
            formdata=f_data,
            callback=self.after_attend,
            dont_filter=True
        )

    # 打刻後
    def after_attend(self, response):
        post_ss(response)


def run_spider(spider):
    '''
    スパイダーを実行する関数
    '''
    def f(q):
        try:
            runner = CrawlerRunner()
            deferred = runner.crawl(spider)
            deferred.addBoth(lambda _: reactor.stop())
            reactor.run()
            q.put(None)
        except Exception as e:
            print(e)
            q.put(e)

    q = Queue()
    p = Process(target=f, args=(q,))
    p.start()
    result = q.get()
    p.join()

def get_user_info(su):
    '''
    ユーザー情報を取得
    '''
    global fpath
    # json モジュールをインポート
    import json 
    # jsonファイルを読み込む
    f = open(fpath)
    d = json.load(f)
    f.close()
    return [d[i] for i in range(len(d)) if d[i]["slack_user_name"] == su][0]

def post_ss(response):
    '''
    Chromeでスクショを取る。
    GUI環境とChromeがあることが前提
    '''
    # エンコーディング判別
    guess = chardet.detect(response.body)
    # Unicode化
    unicode_data = response.body.decode(guess['encoding'])

    # レスポンスとhtmlファイルにして保存
    global curpath
    fname = curpath + '/tmp.html'
    # 書き込みモードで開く
    f = open(fname, 'w') 
    # 引数の文字列をファイルに書き込む
    f.write(unicode_data) 
    # ファイルを閉じる
    f.close() 

    # htmlファイルを画像ファイルに変換
    tmp_img_file = './my_screenshot.png'
    DRIVER = './chromedriver'
    driver = webdriver.Chrome(DRIVER)
    driver.get('file://' + fname)
    driver.save_screenshot(tmp_img_file)
    driver.quit()

    # slackerで送信
    from slackbot_settings import API_TOKEN
    token = API_TOKEN
    # 投稿するチャンネル名
    global channel_info
    c_name = channel_info['name']
 
    # 投稿
    slacker = Slacker(token)
    slacker.files.upload(tmp_img_file, channels=[c_name], title='打刻後のスクショ')

@listen_to('おは')
def start_work(message):

    global user_info
    global channel_info
    global v_info

    user_info       = None
    channel_info    = None

    # ユーザー名を取得
    send_user = message.channel._client.users[message.body['user']]['name']
    user_info = get_user_info(send_user)

    # チャンネル名を取得
    channel_info = message.channel._client.channels[message.body['channel']]

    # ユーザー情報が存在すれば打刻処理を行う
    if user_info:
        run_spider(TimeStampSpider)

        message.reply('{}、おはよう!\r出勤打刻しといたよ＾＾ {}'.format(send_user, v_info))
    else:
        message.reply('{}さん、おはよう!'.format(send_user))

@listen_to('おつ')
def finish_work(message):

    global user_info
    global channel_info
    global v_info

    user_info       = None
    channel_info    = None

    # ユーザー名を取得
    send_user = message.channel._client.users[message.body['user']]['name']
    user_info = get_user_info(send_user)

    # チャンネル名を取得
    channel_info = message.channel._client.channels[message.body['channel']]

    # ユーザー情報が存在すれば打刻処理を行う
    if user_info:
        run_spider(TimeStampFinishSpider)

        message.reply('{}、お疲れ様。\r退勤打刻しといたよ＾＾ {}'.format(send_user, v_info))
    else:
        message.reply('{}さん、お疲れ様。'.format(send_user))


