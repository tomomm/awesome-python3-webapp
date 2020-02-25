import asyncio,logging,aiomysql

# 用来打印 sql语句 日志的 方法
def log(sql,args=()):
    logging.info('SQL: %s' % sql)

# 创建全局连接池
async def create_pool(loop,**kw):
    logging.info('create database connection pool...')
    global __pool
    __pool = await aiomysql.create_pool(
        host = kw.get('host','localhost'),
        port = kw.get('port',3306),
        user = kw['user'],
        password = kw['password'],
        db = kw['db'],
        charset = kw.get('charset','utf-8'),
        autocommit = kw.get('autocommit',True),
        maxsize = kw.get('maxsize',10),
        minsize = kw.get('minsize',1),
        loop = loop
    )

# 使用select函数执行 SQL SELECT语句
# 返回 查询结果集
async def select(sql, args, size=None):
    log(sql,args)
    global __pool
    # with 相当于 try... finally... 不进行异常捕获
    with (await __pool) as conn:
        cur = await conn.cursor(aiomysql.DictCursor)
        # SQL语句的占位符是 ？，而MySQL的占位符 %s，在此替换
        await cur.execute(sql.replace('?', '%s'), args or ())
        if size:
            rs = await cur.fetchmany(size)
        else:
            rs = await cur.fetchall()
        await cur.close()
        logging.info('rows returned: %s' % len(rs))
        return rs

# 使用execute函数执行 INSERT，UPDATE，DELETE语句
# 通过rowcount 返回 结果数
async def execute(sql, args):
    log(sql)
    with (await __pool) as conn:
        try:
            cur = await conn.cursor()
            await cur.execute(sql.replace('?','%s'), args)
            affected = cur.rowcount
            await cur.close()
        except BaseException as e:
            raise
        return affected

class Model(dict, metaclass=ModelMetaclass):
    def __init(self,**kw):
        super(Model, self).__init__(**kw)
        pass
