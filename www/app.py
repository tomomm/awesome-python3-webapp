import logging
logging.basicConfig(level=logging.INFO,
                    format='%(levelname)s:%(filename)s'
                           '[%(lineno)d]:%(threadName)s: %(message)s' )  # 日志内容
                         #  ' - %(asctime)s', datefmt='[%d/%b/%Y %H:%M:%S]')  # 日志时间
import asyncio, os, json, time
from datetime import datetime
from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import www.orm as orm
from www.coroweb import add_static,add_routes

from conf.config import configs

## handlers 是url处理模块，当handlers.py在API章节里完全编辑完再将下一行代码的双井号去掉
from www.handlers import cookie2user , COOKIE_NAME
import www.handlers

## 初始化jinja2的函数
def init_jinja2(app, **kw):
    logging.info('init jinja2')
    options = dict(
        autoescape = kw.get('autoescape', True),
        block_start_string = kw.get('block_start_string', '{%'),
        block_end_string = kw.get('block_end_string', '%}'),
        variable_start_string = kw.get('variable_start_string', '{{'),
        variable_end_string = kw.get('variable_end_string','}}'),
        auto_reload = kw.get('auto_reload_', True)
    )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'templates')
        logging.info('set jinja2 template path: %s' % path)
        env = Environment(loader=FileSystemLoader(path), **options)
        filters = kw.get('filters',None)
        if filters is not None:
            for name, f in filters.items():
                env.filters[name] = f
        app['__templating__'] = env

## 以下是middleware，可以把通用的功能从每个URL处理函数中拿出来集中放到一个地方
## URL处理日志工厂
async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request: %s %s' % (request.method, request.path))
        return (await handler(request))
    return logger

## 认证处理工厂-- 把当前用户绑定到request上， 并对URL/manage/进行拦截，检查当前用户是否是管理员身份
## 需要handlers.py的支持， 当handlers.py在API章节里完全编辑再将下班代码的双井号去掉
async def auth_factory(app, handler):
   async def auth(request):
       logging.info('check user: %s %s' % (request.method, request.path))
       request.__user__ = None
       cookie_str = request.cookies.get(COOKIE_NAME)
       if cookie_str:
           user = await cookie2user(cookie_str)
           if user:
               logging.info('set current user: %s' % user.email)
               request.__user__ = user
       if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
           return web.HTTPFound('/signin')
       return (await handler(request))
   return auth

## 数据处理工厂
async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == 'POST':
            ## startswith(str,beg=0,end=len(string)) 检查某字符串是否以 指定字符串str开头
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request from: %s' % str(request.__data__))
        return (await handler(request))
    return parse_data

## 响应返回处理工厂
async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler...')
        r = await handler(request)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body = r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(r, dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                ## 在handlers.py完全完成后，去掉下一行双井号
                r['__user__'] = request.__user__
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and t >=100 and t < 600:
                return web.Response(t, str(m))

        # default:
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response

## 自定义 jinja2 时间转换过滤器
def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta//60)
    if delta < 86400:
        return u'%s小时前' % (delta//3600)
    if delta < 604800:
        return u'%s天前' % (delta//86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

async def init(loop):
    await orm.create_pool(loop=loop, **configs.db)
    app = web.Application(loop=loop, middlewares=[
        logger_factory, response_factory, auth_factory
    ])

    init_jinja2(app, filters=dict(datetime=datetime_filter))
    # 在 handlers.py 完成后， 去掉下一行井号
    add_routes(app, 'handlers')  #注册handlers中的 URL函数
    add_static(app)

    # DeprecationWarning: Application.make_handler(...) is deprecated, use AppRunner API instead
    # srv = await loop.create_server(app.make_handler(),'127.0.0.1', 9000)
    srv = await loop.create_server(app.make_handler(),'127.0.0.1', 9000)  #过时用法，已弃用。
    # web.run_app(app,host='127.0.0.1',port=9000)
    logging.info('server started at http://127.0.0.1:9000')
    return srv

# def index(request):
#     return web.Response(body=b'<h1>Awesome</h1>',content_type="text/html")
#
# async def index(request):
#     return web.Response(body=b'<h1>Awesome Website</h1>',content_type='text/html')

# def init():
#     app = web.Application()
#     app.router.add_get('/',index)
#     web.run_app(app,host='127.0.0.1',port=9000)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init(loop))
    loop.run_forever()

    # init(loop)