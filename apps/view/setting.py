#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#设置页面
import locale
from flask import Blueprint, render_template, request, redirect, session
from flask_babel import gettext as _
from apps.base_handler import *
from apps.back_end.db_models import *
from config import *

bpSetting = Blueprint('bpSetting', __name__)

supported_languages = ['zh_cn', 'tr_tr', 'en']

#各种语言的语种代码和文字描述的对应关系
def LangMap(): 
    return {"zh-cn": _("Chinese"),
        "en-us": _("English"),
        "fr-fr": _("French"),
        "es-es": _("Spanish"),
        "pt-br": _("Portuguese"),
        "de-de": _("German"),
        "it-it": _("Italian"),
        "ja-jp": _("Japanese"),
        "ru-ru": _("Russian"),
        "tr-tr": _("Turkish"),
        "ko-kr": _("Korean"),
        "ar": _("Arabic"),
        "cs": _("Czech"),
        "nl": _("Dutch"),
        "el": _("Greek"),
        "hi": _("Hindi"),
        "ms": _("Malaysian"),
        "bn": _("Bengali"),
        "fa": _("Persian"),
        "ur": _("Urdu"),
        "sw": _("Swahili"),
        "vi": _("Vietnamese"),
        "pa": _("Punjabi"),
        "jv": _("Javanese"),
        "tl": _("Tagalog"),
        "ha": _("Hausa"),}

@bpSetting.route("/setting", endpoint='Setting')
@login_required()
def Setting(tips=None):
    user = get_login_user()
    return render_template('setting.html', tab='set', user=user, tips=tips, mailSender=SRC_EMAIL, langMap=LangMap())

@bpSetting.post("/setting", endpoint='SettingPost')
@login_required()
def SettingPost():
    user = get_login_user()
    form = request.form
    keMail = form.get('kindle_email')
    myTitle = form.get('rss_title')
    if not keMail:
        tips = _("Kindle E-mail is requied!")
    elif not myTitle:
        tips = _("Title is requied!")
    else:
        user.kindle_email = keMail.strip(';, ')
        user.timezone = int(form.get('timezone', TIMEZONE))
        user.send_time = int(form.get('send_time', '0'))
        user.enable_send = bool(form.get('enable_send'))
        user.book_type = form.get('book_type', 'epub')
        user.device = form.get('device_type', 'kindle')
        user.use_title_in_feed = bool(form.get('title_from') == 'feed')
        user.title_fmt = form.get('title_fmt')
        alldays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        user.send_days = [day for day in alldays if form.get(day)]
        user.merge_books = bool(form.get('merge_books'))
        user.book_mode = form.get('bookmode')
        user.remove_hyperlinks = form.get('removehyperlinks')
        user.author_format = form.get('author_format')
        user.save()

        myFeedBook = user.my_rss_book
        if myFeedBook:
            myFeedBook.language = form.get("book_language", "en-us")
            myFeedBook.title = myTitle
            myFeedBook.keep_image = bool(form.get("keep_image"))
            myFeedBook.oldest_article = int(form.get('oldest', 7))
            myFeedBook.users = [user.name] if form.get('enable_rss') else []
            myFeedBook.save()
        tips = _("Settings Saved!")

    return render_template('setting.html', tab='set', user=user, tips=tips, mailSender=SRC_EMAIL, langMap=LangMap())

#设置国际化语种
@bpSetting.route("/setlocale/<langCode>")
def SetLang(langCode):
    global supported_languages
    print(f'lang: {langCode}')
    langCode = langCode.lower()
    if langCode not in supported_languages:
        langCode = "en"
    session['langCode'] = langCode
    return redirect('/')
