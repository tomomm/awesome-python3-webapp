import asyncio, re, time, json, logging, hashlib, base64

## markdown 是处理日志文本的一种格式语法。
import markdown
from aiohttp import web
from www.coroweb import get, post

## 分页管理 以及调取API时的错误信息
from www.apis import Page, APIValueError, APIResourceNotFoundError, APIPermissionError,APIError
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
#########################  页面处理
## 处理首页URL
@get('/')
async def index(*, page = '1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        blogs = []
    else:
        blogs = await Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return {
        '__template__': 'blogs.html',
        'page': p,
        'blogs': blogs
    }

## 处理注册页面URL
@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }

## 处理登录页面URL
@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }

## 用户注销
@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-delete-', max_age=0, httponly=True)
    logging.info('user sign out.')
    return r

## 获取管理页面
@get('/manage/')
def manage():
    return 'redirect:/manage/comments'

## 日志管理页面
@get('/manage/blogs')
def manage_blogs(*, page='1'):
    return {
        '__template__': 'manage_blogs.html',
        'page_index': get_page_index(page)
    }

## 创建日志页面
@get('/manage/blogs/create')
def manage_create_blog():
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs'
    }

## 评论管理页面
@get('/manage/comments')
def manage_comments(*, page='1'):
    return {
        '__template__': 'manage_comments.html',
        'page_index': get_page_index(page)
    }

## 用户管理页面
@get('/manage/users')
def manage_users(*, page='1'):
    return {
        '__template__': 'manage_users.html',
        'page_index': get_page_index(page)
    }

## 处理日志详情页面
@get('/blog/{id}')
async def get_blog(id):
    blog = await Blog.find(id)
    comments = await Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
    for c in comments:
        c.html_content = markdown.markdown(c.content)
    blog.html_content = markdown.markdown(blog.content)
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }


################################  API处理
## 用户登录验证API
@post('/api/authenticate')
async def authenticate(*, email, passwd):
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not passwd:
        raise APIValueError('passwd', 'Invalid password.')
    users = await User.findAll('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]
    # check passwd:
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', 'Invalid password.')
    # authenticate ok ,set cookie:
    r = web.Response()
    r.set_cookie(name=COOKIE_NAME, value=user2cookie(user, 86400), max_age=86400, httponly=True)

    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


## 定义EMAIL和HASH的格式规范
_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0=9a-f]{40}$')

## 用户注册API
@post('/api/users')
async def api_register_user(*, email, name, passwd):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or _RE_SHA1.match('passwd'):
        raise APIValueError('passwd')
    users = await User.findAll('email=?', [email])
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    # make session cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

## 删除用户api
@post('/api/users/{id}/delete')
async def api_delete_users(id, request):
    check_admin(request)
    id_buff = id
    user = await User.find(id)
    if user is None:
        raise APIResourceNotFoundError('Comment')
    await user.remove()
    # 给被删除的用户在评论中标记
    comments = await Comment.findAll('user_id=?',[id])
    if comments:
        for comment in comments:
            id = comment.id
            c = await Comment.find(id)
            c.suer_name = c.user_name + '（该用户已被删除）'
            await c.update()
    id = id_buff
    return dict(id=id)


## 获取用户信息api
@get('/api/users')
async def api_get_users(*, page='1'):
    page_index = get_page_index(page)
    num = await User.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    users = await User.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    for u in users:
        u.passwd = '******'
    return dict(page=p, users=users)


## 获取日志详情api
@get('/api/blogs/{id}')
async def api_get_blog(*, id):
    blog = await Blog.find(id)

## 获取日志列表api
@get('/api/blogs')
async def api_blogs(*, page='1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, blogs=())
    blogs = await Blog.findAll(orderBy='create_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)

## 发表日志API
@post('/api/blogs')
async def api_create_blog(request,* , name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty')
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image,name=name.strip(),summary=summary.strip(),content=content.strip())
    await blog.save()
    return blog

## 用户发表评论API
@post('/api/blogs/{id}/comments')
async def api_create_comment(id, request, *, content):
    user = request.__user__
    if user is None:
        raise APIPermissionError('Please signin first.')
    if not content or not content.strip():
        raise APIValueError('content')
    blog = await Blog.find(id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image, content=content.strip())
    await comment.save()
    return comment

## 过去评论信息api
@get('/api/comments')
async def api_comments(*, page='1'):
    page_index = get_page_index(page)
    num = await Comment.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, comments=())
    comments = await Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)

## 管理员删除评论api
@post('/api/comments/{id}/delete')
async def api_delete_comments(id, request):
    check_admin(request)
    c = await Comment.find(id)
    if c is None:
        raise APIResourceNotFoundError('Comment')
    await c.remove()
    return dict(id=id)