#!/usr/bin/env python3
# -*- coding:utf-8 -*-
#一些高级设置功能页面

import datetime, io, textwrap
from urllib.parse import quote, unquote, urljoin, urlparse
from flask import Blueprint, url_for, render_template, redirect, session, send_file, abort, current_app as app
from flask_babel import gettext as _
from PIL import Image
from ..base_handler import *
from ..back_end.db_models import *
from ..utils import ke_encrypt, ke_decrypt, str_to_bool, safe_eval, xml_escape, xml_unescape
from ..lib.pocket import Pocket
from ..lib.wallabag import WallaBag
from ..lib.urlopener import UrlOpener

bpAdv = Blueprint('bpAdv', __name__)

def adv_render_template(tpl, advCurr, **kwargs):
    kwargs.setdefault('tab', 'advset')
    kwargs.setdefault('tips', '')
    kwargs.setdefault('adminName', app.config['ADMIN_NAME'])
    return render_template(tpl, advCurr=advCurr, **kwargs)

#现在推送
@bpAdv.route("/adv", endpoint='AdvDeliverNowEntry')
@bpAdv.route("/adv/delivernow", endpoint='AdvDeliverNow')
@login_required()
def AdvDeliverNow():
    user = get_login_user()
    recipes = user.get_booked_recipe()
    return adv_render_template('adv_delivernow.html', 'deliverNow', user=user, recipes=recipes)

#设置邮件白名单
@bpAdv.route("/adv/whitelist", endpoint='AdvWhiteList')
@login_required()
def AdvWhiteList():
    user = get_login_user()
    if app.config['DATABASE_URL'] == 'datastore':
        mailHost = 'appid.appspotmail.com'
    else:
        mailHost = urlparse(app.config['APP_DOMAIN']).netloc.split(':')[0]
    
    return adv_render_template('adv_whitelist.html', 'whitelist', user=user, mailHost=mailHost)
    
@bpAdv.post("/adv/whitelist", endpoint='AdvWhiteListPost')
@login_required()
def AdvWhiteListPost():
    user = get_login_user()
    wlist = request.form.get('wlist')
    if wlist:
        wlist = wlist.replace('"', "").replace("'", "").strip()
        if wlist.startswith('*@'): #输入*@xx.xx则修改为@xx.xx
            wlist = wlist[1:]
        if wlist:
            WhiteList.get_or_create(mail=wlist, user=user.name)
    return redirect(url_for('bpAdv.AdvWhiteList'))
    
#删除白名单项目
@bpAdv.route("/advdel", endpoint='AdvDel')
@login_required()
def AdvDel():
    user = get_login_user()
    wlist_id = request.args.get('wlist_id')
    if wlist_id:
        dbItem = WhiteList.get_by_id_or_none(wlist_id)
        if dbItem:
            dbItem.delete_instance()
        return redirect(url_for("bpAdv.AdvWhiteList"))
    return redirect(url_for("bpAdmin.Admin"))

#设置归档和分享配置项
@bpAdv.route("/adv/archive", endpoint='AdvArchive')
@login_required()
def AdvArchive():
    user = get_login_user()

    #jinja自动转义非常麻烦，在代码中先把翻译写好再传过去吧
    appendStrs = {}
    appendStrs["Evernote"] = _("Append hyperlink '{}' to article").format(_('Save to {}').format(_('evernote')))
    appendStrs["Wiz"] = _("Append hyperlink '{}' to article").format(_('Save to {}').format(_('wiz')))
    appendStrs["Pocket"] = _("Append hyperlink '{}' to article").format(_('Save to {}').format(_('pocket')))
    appendStrs["Instapaper"] = _("Append hyperlink '{}' to article").format(_('Save to {}').format(_('instapaper')))
    appendStrs["wallabag"] = _("Append hyperlink '{}' to article").format(_('Save to {}').format(_('wallabag')))
    appendStrs["Weibo"] = _("Append hyperlink '{}' to article").format(_('Share on {}').format(_('weibo')))
    appendStrs["Facebook"] = _("Append hyperlink '{}' to article").format(_('Share on {}').format(_('facebook')))
    appendStrs["X"] = _("Append hyperlink '{}' to article").format(_('Share on {}').format('X'))
    appendStrs["Tumblr"] = _("Append hyperlink '{}' to article").format(_('Share on {}').format(_('tumblr')))
    appendStrs["Browser"] = _("Append hyperlink '{}' to article").format(_('Open in browser'))
    appendStrs["Qrcode"] = _("Append qrcode of url to article")
    shareLinks = user.share_links
    shareLinks.pop('key', None)
    
    return adv_render_template('adv_archive.html', 'archive', user=user, appendStrs=appendStrs,
        shareLinks=shareLinks, ke_decrypt=ke_decrypt)

@bpAdv.post("/adv/archive", endpoint='AdvArchivePost')
@login_required()
def AdvArchivePost():
    user = get_login_user()
    form = request.form
    evernoteMail = form.get('evernote_mail', '').strip()
    evernote = str_to_bool(form.get('evernote')) and evernoteMail
    wizMail = form.get('wiz_mail', '').strip()
    wiz = str_to_bool(form.get('wiz')) and wizMail
    pocket = str_to_bool(form.get('pocket'))
    instapaper = str_to_bool(form.get('instapaper'))
    instaName = form.get('instapaper_username', '').strip()
    instaPwd = form.get('instapaper_password', '')

    wallabag = str_to_bool(form.get('wallabag'))
    wallaHost = form.get('wallabag_host', '')
    wallaUsername = form.get('wallabag_username', '')
    wallaPassword = form.get('wallabag_password', '')
    wallaId = form.get('wallabag_client_id', '')
    wallaSecret = form.get('wallabag_client_secret', '')
    if not all((wallaHost, wallaUsername, wallaPassword, wallaId, wallaSecret)):
        wallabag = False

    #将instapaper/wallabag的密码加密
    if instaName and instaPwd:
        instaPwd = user.encrypt(instaPwd)
    else:
        instaName = ''
        instaPwd = ''
    if wallaUsername and wallaPassword:
        wallaPassword = user.encrypt(wallaPassword)
    else:
        wallaUsername = ''
        wallaPassword = ''
    
    shareLinks = user.share_links
    pocketToken = shareLinks.get('pocket', {}).get('access_token', '')
    oldWalla = shareLinks.get('wallabag', {})
    newWalla = oldWalla.copy()
    newWalla.update({'enable': '1' if wallabag else '', 'host': wallaHost, 'username': wallaUsername,
        'password': wallaPassword, 'client_id': wallaId, 'client_secret': wallaSecret})
    if newWalla != oldWalla: #如果任何数据有变化，清除之前的token
        newWalla['access_token'] = ''
        newWalla['refresh_token'] = ''
    
    shareLinks['Evernote'] = {'enable': '1' if evernote else '', 'email': evernoteMail}
    shareLinks['Wiz'] = {'enable': '1' if wiz else '', 'email': wizMail}
    shareLinks['Pocket'] = {'enable': '1' if pocket else '', 'access_token': pocketToken}
    shareLinks['Instapaper'] = {'enable': '1' if instapaper else '', 'username': instaName, 'password': instaPwd}
    shareLinks['wallabag'] = newWalla
    shareLinks['Weibo'] = str_to_bool(form.get('weibo'))
    shareLinks['Facebook'] = str_to_bool(form.get('facebook'))
    shareLinks['X'] = str_to_bool(form.get('x'))
    shareLinks['Tumblr'] = str_to_bool(form.get('tumblr'))
    shareLinks['Browser'] = str_to_bool(form.get('browser'))
    shareLinks['Qrcode'] = str_to_bool(form.get('qrcode'))
    user.share_links = shareLinks
    user.save()
    return redirect(url_for("bpAdv.AdvArchive"))

#导入自定义rss订阅列表，当前支持Opml格式
@bpAdv.route("/adv/import", endpoint='AdvImport')
@login_required()
def AdvImport(tips=None):
    user = get_login_user()
    return adv_render_template('adv_import.html', 'import', user=user, tips=tips)

@bpAdv.post("/adv/import", endpoint='AdvImportPost')
@login_required()
def AdvImportPost():
    import opml
    user = get_login_user()
    upload = request.files.get('import_file')
    defaultIsFullText = bool(request.form.get('default_is_fulltext')) #默认是否按全文RSS导入
    if upload:
        try:
            rssList = opml.from_string(upload.read())
        except Exception as e:
            return adv_render_template('adv_import.html', 'import', user=user, tips=str(e))

        #兼容老版本的转义
        isKindleEarOpml = False
        ownerElem = rssList._tree.xpath('/opml/head/ownerName')
        if ownerElem and ownerElem[0].text == 'KindleEar':
            isKindleEarOpml = True
        
        for o in walkOpmlOutline(rssList):
            if o.text and not o.title and isKindleEarOpml: #老版本只有text属性，没有title属性
                title, url, isfulltext = o.text, unquote_plus(o.xmlUrl), o.isFulltext #isFulltext为非标准属性
            else:
                title, url, isfulltext = xml_unescape(o.text or o.title), xml_unescape(o.xmlUrl), o.isFulltext
            isfulltext = str_to_bool(isfulltext) if isfulltext else defaultIsFullText
            
            if not url.startswith('http'):
                url = ('https:/' if url.startswith('/') else 'https://') + url

            if title and url: #查询是否有重复的
                dbItem = Recipe.get_or_none((Recipe.user == user.name) & (Recipe.title == title))
                if dbItem:
                    dbItem.url = url
                    dbItem.isfulltext = isfulltext
                    dbItem.save()
                else:
                    Recipe.create(title=title, url=url, user=user.name, isfulltext=isfulltext, type_='custom')
                        
        return redirect(url_for("bpSubscribe.MySubscription"))
    else:
        return redirect(url_for("bpAdv.AdvImport"))
    
#遍历opml的outline元素，支持不限层数的嵌套
def walkOpmlOutline(outline):
    if not outline:
        return
    
    cnt = len(outline)
    for idx in range(cnt):
        obj = outline[idx]
        if len(obj) > 0:
            yield from walkOpmlOutline(obj)
        yield obj

#生成自定义rss订阅列表的Opml格式文件，让用户下载保存
@bpAdv.route("/adv/export", endpoint='AdvExport')
@login_required()
def AdvExport():
    user = get_login_user()
    
    #为了简单起见，就不用其他库生成xml，而直接使用字符串格式化生成
    opmlTpl = textwrap.dedent("""\
    <?xml version="1.0" encoding="utf-8" ?>
    <opml version="2.0">
    <head>
      <title>KindleEar.opml</title>
      <dateCreated>{date}</dateCreated>
      <dateModified>{date}</dateModified>
      <ownerName>KindleEar</ownerName>
      <createdBy>KindleEar {appVer}</createdBy>
    </head>
    <body>
    {outLines}
    </body>
    </opml>""")

    date = user.local_time('%a, %d %b %Y %H:%M:%S UTC%z')
    outLines = []
    for feed in user.all_custom_rss():
        isfulltext = 'yes' if feed.isfulltext else 'no'
        outLines.append('<outline type="rss" text="{0}" title="{0}" xmlUrl="{1}" isFulltext="{2}" />'.format(
            xml_escape(feed.title), xml_escape(feed.url), isfulltext))
    outLines = '\n'.join(outLines)
    
    opmlFile = opmlTpl.format(date=date, appVer=appVer, outLines=outLines).encode('utf-8')
    return send_file(io.BytesIO(opmlFile), mimetype="text/xml", as_attachment=True, download_name="KindleEar_subscription.xml")
    
#在本地选择一个图片上传做为自定义RSS书籍的封面
@bpAdv.route("/adv/cover")
@login_required()
def AdvUploadCoverImage(tips=None):
    user = get_login_user()
    covers = {}
    covers['order'] = user.covers.get('order', 'random')
    for idx in range(7):
        coverName = f'cover{idx}'
        covers[coverName] = user.covers.get(coverName, f'/images/{coverName}.jpg')
    jsonCovers = json.dumps(covers)
    return adv_render_template('adv_uploadcover.html', 'uploadCover', user=user, tips=tips,
        uploadUrl=url_for("bpAdv.AdvUploadCoverAjaxPost"), covers=covers, jsonCovers=jsonCovers)

#AJAX接口的上传封面图片处理函数
@bpAdv.post("/adv/cover", endpoint='AdvUploadCoverAjaxPost')
@login_required(forAjax=True)
def AdvUploadCoverAjaxPost():
    MAX_WIDTH = 832
    MAX_HEIGHT = 1280
    ret = {'status': 'ok'}
    user = get_login_user()
    covers = user.covers
    covers['order'] = request.form.get('order', 'random')
    for idx in range(7):
        coverName = f'cover{idx}'
        upload = request.files.get(coverName) or request.form.get(coverName)
        if not upload:
            continue

        if isinstance(upload, str):
            if upload.startswith('/images/'): #delete the old image data
                UserBlob.delete().where((UserBlob.user == user.name) & (UserBlob.name == coverName)).execute()
            covers[coverName] = upload
            continue
        
        try:
            #将图像转换为JPEG格式，同时限制分辨率不超过 832x1280，宽高比为0.625~0.664，建议0.65
            imgInst = Image.open(upload)
            width, height = imgInst.size
            fmt = imgInst.format
            if (width > MAX_WIDTH) or (height > MAX_HEIGHT):
                ratio = min(MAX_WIDTH / width, MAX_HEIGHT / width)
                imgInst = imgInst.resize((int(width * ratio), int(height * ratio)))
            if imgInst.mode != 'RGB':
                imgInst = imgInst.convert('RGB')
            data = io.BytesIO()
            imgInst.save(data, 'JPEG')
            dbCover = UserBlob.get_or_none((UserBlob.user == user.name) & (UserBlob.name == coverName))
            if dbCover:
                dbCover.data = data.getvalue()
            else:
                dbCover = UserBlob(name=coverName, user=user.name, data=data.getvalue())
            dbCover.save()
            covers[coverName] = '/dbimage/{}'.format(str(dbCover.id))
            upload.close()
        except Exception as e:
            ret['status'] = str(e)
            return ret
    
    user.covers = covers
    user.save()
    ret.update(covers)
    return ret

#在本地选择一个样式文件上传做为所有书籍的样式
@bpAdv.route("/adv/css", endpoint='AdvUploadCss')
@login_required()
def AdvUploadCss(tips=None):
    user = get_login_user()
    extra_css = user.get_extra_css()
    return adv_render_template('adv_uploadcss.html', 'uploadCss', extra_css=extra_css,
        user=user, uploadUrl=url_for("bpAdv.AdvUploadCssAjaxPost"), 
        deleteUrl=url_for("bpAdv.AdvDeleteCssAjaxPost"), tips=tips)

#AJAX接口的上传CSS处理函数
@bpAdv.post("/adv/css", endpoint='AdvUploadCssAjaxPost')
@login_required(forAjax=True)
def AdvUploadCssAjaxPost():
    ret = {'status': 'ok'}
    user = get_login_user()
    try:
        upload = request.files.get('css_file')
        data = upload.read().decode('utf-8').encode('utf-8') #测试是否是utf-8编码
        dbItem = UserBlob.get_or_none((UserBlob.user == user.name) & (UserBlob.name == 'css'))
        if dbItem:
            dbItem.data = data
        else:
            dbItem = UserBlob(name='css', user=user.name, data=data)
        dbItem.save()
        upload.close()
    except Exception as e:
        ret['status'] = str(e)

    return ret

#删除上传的CSS
@bpAdv.post("/adv/css/delete", endpoint='AdvDeleteCssAjaxPost')
@login_required(forAjax=True)
def AdvDeleteCssAjaxPost():
    ret = {'status': 'ok'}
    user = get_login_user()
    if request.form.get('action') == 'delete':
        UserBlob.delete().where((UserBlob.user == user.name) & (UserBlob.name=='css')).execute()
    
    return ret

#设置calibre的参数
@bpAdv.route("/adv/calibre", endpoint='AdvCalibreOptions')
@login_required()
def AdvCalibreOptions(tips=None):
    user = get_login_user()
    options = json.dumps(user.custom.get('calibre_options', {}), indent=2)
    return adv_render_template('adv_calibre_options.html', 'calibreOptions', options=options, user=user)

#设置calibre的参数
@bpAdv.post("/adv/calibre", endpoint='AdvCalibreOptionsPost')
@login_required()
def AdvCalibreOptionsPost():
    user = get_login_user()
    tips = ''
    txt = request.form.get('options', '').strip()
    try:
        options = safe_eval(txt) if txt else {}
        if isinstance(options, dict):
            custom = user.custom
            custom['calibre_options'] = options
            user.custom = custom
            user.save()
            tips = _("Settings Saved!")
        else:
            tips = _('The format is invalid.')
    except Exception as e:
        tips = str(e)

    options = json.dumps(user.custom.get('calibre_options', {}), indent=2)
    return adv_render_template('adv_calibre_options.html', 'calibreOptions', tips=tips, options=options, user=user)

#读取数据库中的图像二进制数据，如果为dbimage/cover则返回当前用户的封面图片
@bpAdv.route("/dbimage/<id_>", endpoint='DbImage')
@login_required()
def DbImage(id_):
    user = get_login_user()
    dbItem = UserBlob.get_by_id_or_none(id_)
    if dbItem:
        return send_file(io.BytesIO(dbItem.data), mimetype='image/jpeg')
    else:
        abort(404)

#集成各种网络服务OAuth2认证的相关处理
@bpAdv.route("/oauth2/<authType>", endpoint='AdvOAuth2')
@login_required()
def AdvOAuth2(authType):
    if authType.lower() != 'pocket':
        return 'Auth Type ({}) Unsupported!'.format(authType)
        
    user = get_login_user()
    cbUrl = urljoin(app.config['APP_DOMAIN'], '/oauth2cb/pocket?redirect={}'.format(url_for("bpAdv.AdvArchive")))
    pocket = Pocket(app.config['POCKET_CONSUMER_KEY'], cbUrl)
    try:
        request_token = pocket.get_request_token()
        url = pocket.get_authorize_url(request_token)
    except Exception as e:
        return render_template('tipsback.html', title='Authorization Error', urltoback=url_for('bpAdv.AdvArchive'),
            tips=_('Authorization Error!<br/>{}').format(str(e)))

    session['pocket_request_token'] = request_token
    return redirect(url)
        
#OAuth2认证过程的回调
@bpAdv.route("/oauth2cb/<authType>", endpoint='AdvOAuth2Callback')
@login_required()
def AdvOAuth2Callback(authType):
    if authType.lower() != 'pocket':
        return 'Auth Type ({}) Unsupported!'.format(authType)
        
    user = get_login_user()
    
    pocket = Pocket(app.config['POCKET_CONSUMER_KEY'])
    request_token = session.get('pocket_request_token', '')
    shareLinks = user.share_links
    try:
        acToken = pocket.get_access_token(request_token)
        shareLinks.setdefault('pocket', {})
        shareLinks['pocket']['access_token'] = acToken
        user.share_links = shareLinks
        user.save()
        return render_template('tipsback.html', title='Success authorized', urltoback=url_for('bpAdv.AdvArchive'), tips=_('Success authorized by Pocket!'))
    except Exception as e:
        shareLinks['pocket'] = {'enable': '', 'access_token': ''}
        user.share_links = shareLinks
        user.save()
        return render_template('tipsback.html', title='Failed to authorize', urltoback=url_for('bpAdv.AdvArchive'), 
            tips=_('Failed to request authorization of Pocket!<hr/>See details below:<br/><br/>{}').format(e))

#通过AJAX验证密码等信息的函数
@bpAdv.post("/verifyajax/<verifType>", endpoint='VerifyAjaxPost')
@login_required()
def VerifyAjaxPost(verifType):
    user = get_login_user()
    form = request.form
    respDict = {'status': 'ok'}
    if verifType == 'instapaper':
        INSTAPAPER_API_AUTH_URL = "https://www.instapaper.com/api/authenticate"
        userName = form.get('username', '')
        password = form.get('password', '')
        opener = UrlOpener()
        apiParameters = {'username': userName, 'password':password}
        ret = opener.open(INSTAPAPER_API_AUTH_URL, data=apiParameters)
        if ret.status_code in (200, 201):
            respDict['correct'] = 1
        elif ret.status_code == 403:
            respDict['correct'] = 0
        else:
            respDict['correct'] = 0
            respDict['status'] = _("The Instapaper service encountered an error. Please try again later.")
    elif verifType == 'wallabag':
        host = form.get('host', '')
        name = form.get('username', '')
        passwd = form.get('password', '')
        id_ = form.get('client_id', '')
        secret = form.get('client_secret', '')
        config = {'host': host, 'username': name, 'password': passwd, 'client_id': id_, 
            'client_secret': secret}
        wallabag = WallaBag(config, default_log)
        msg = wallabag.update_token()
        return {'status': msg or 'ok'}
    else:
        respDict['status'] = _('Request type [{}] unsupported').format(verifType)
    return respDict
    