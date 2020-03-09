import asyncio, re, time, json, logging, hashlib, base64

## markdown 是处理日志文本的一种格式语法。
import markdown
from aiohttp import web
from www.coroweb import get, post

## 分页管理 以及调取API时的错误信息
from www.apis import Page, APIValueError, APIResourceNotFoundError, APIPermissionError
from www.models import User, Comment, Blog, next_id
from conf.config import configs

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

## 查看是否是管理员用户
def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()

## 获取页码信息
def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p

## 计算加密cookie
def user2cookie(user, max_age):
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

## 文本转HTML
def text2html(text):
    ## map(func, iterable) 将可迭代对象iterable 中的每一个元素 根据func函数做映射  如： list(map(lambda x:x*2, [1,2,3])) 返回 [2,4,6]
    ## filter(func, iterable) 过滤器 将iterable可迭代对象 根据判断函数的规则 生成 一个新的迭代器对象
    ## str.strip([char]) 用于移除字符字符串 头尾以char开头或结尾的字符。  默认为去掉字符串首尾两端的空格
    ## str.split(str="", num=string.count(str)) 通过指定分隔符对 字符串str进行切片， 返回分割后的字符串列表。 默认：分隔符为所有的空字符 包括空格，换行，制表符等

    ## 将text 中的每一行都 进行 特殊符号映射crfs
    lines = map(lambda s: '<p>%s</p>' % s.replace('&','&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
    ## 将每行数据连在一起。
    return ''.join(lines)

## 解密cookie
async def cookie2user(cookie_str):
    ## 如果 cookie_str 为空
    if not cookie_str:
        return
    try:
        L = cookie_str.split('-')
        # 如果 L 的元素不为3 ，返回空
        if len(L) != 3:
            return None

        uid, expires, sha1 = L
        # 如果 cookie 已过期， 返回空
        if int(expires) < time.time():
            return None

        user = await User.find(uid)
        if user is None:
            return None

        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None

## 处理首页URL
@get('/')
async def index(*, page = '1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        blogs = []
    else:
        blogs = await Blog.findAll(orderBy='create_at desc', limit=(p.offset, p.limit))
    return {
        '__template__': 'blogs.html',
        'page': p,
        'blogs': blogs
    }