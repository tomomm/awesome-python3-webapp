import asyncio,logging,aiomysql

# 用来打印 sql语句 日志的 方法
def log(sql,args=()):
    logging.info('SQL: %s' % sql)

global __pool

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
        charset = kw.get('charset','utf8'),
        autocommit = kw.get('autocommit',True),
        maxsize = kw.get('maxsize',10),
        minsize = kw.get('minsize',1),
        loop = loop
    )

# 使用select函数执行 SQL SELECT语句
# 返回 查询结果集
async def select(sql, args, size=None):
    '''
    使用select函数执行 SQL SELECT语句
    :param sql:   未赋参数的sql语句
    :param args:  sql语句的参数
    :param size:  返回的结果的数量（默认未全部返回）
    :return:      查询结果集
    '''
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

def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ', '.join(L)

class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):
        # 排除 Model 类本身
        if name == 'Model':
            return type.__new__(cls,name,bases,attrs)
        # 获取 table 名称
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s)' % (name, tableName))
        # 获取所有的 Field 和 主键名
        mappings = dict()
        fields = []
        primaryKey = None
        for k,v in attrs.items():
            if isinstance(v, Field):
                logging.info('  found mapping: %s ==> %s' % (k,v))
                mappings[k] = v
                if v.primary_key:
                    # 找到主键
                    if primaryKey:
                        raise RuntimeError('Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    fields.append(k)

        if not primaryKey:
            raise RuntimeError('Primary key not found.')
        for k in mappings.keys():
            attrs.pop(k)
        escaped_fields = list(map( (lambda f: '`%s`' % f) ,fields)) # map(func, iterable[,..]) map中第一个参数时一个函数， map中后面的参数是第一个函数的参数
                                                                    # 在本语句中 是将 fields列表 根据 lamba f: '`%s`'函数 做映射，返回迭代器。再通过list()转化为列表
        # 利用python的特性 给类创建新属性，并且赋值
        attrs['__mappings__'] = mappings # 保存属性和列的映射关系
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey # 主键属性名
        attrs['__fields__'] = fields # 除主键外的属性名
        # 构造默认的 SELECT, INSERT, UPDATE和DELETE 语句
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields)+1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName,', '.join(map((lambda f: '`%s`=?' % (mappings.get(f).name or f)), fields)),primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases ,attrs)


# ORM映射基类 Model
class Model(dict, metaclass=ModelMetaclass):
    def __init(self,**kw):
        super(Model, self).__init__(**kw)

    #调用不存在类 Model 定义的属性时会进入该方法，动态返回一个属性。 但是本方法暂时没有上述作用。
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    #设定 指定key 的 value
    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self,key):
        return getattr(self,key,None) # getattr(对象,属性名[,默认值]) 用于获取对象的属性

    def getValueOrDefault(self,key):
        value = getattr(self,key,None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                 value = field.default() if callable(field.default) else field.default
                 logging.debug('using default value for %s: %s' % (key,str(value)))
                 setattr(self,key,value) # setattr（object, attribution_name, value） 用于给对象设定属性
        return value

    async def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1:  # 此处含义未知，为什么rows 不等于1 就会失败，下同
            logging.warning('failed to insert record: affected rows: %s' % rows)

    async def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__,args)
        if rows != 1:
            logging.warning('failed to update by primary key: affected rows: %s' % rows)

    async def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__,args)
        if rows != 1:
            logging.warning('failed to remove by primary key: affected rows: %s' % rows)

    # @lassmethod 类方法， 不需要通过 实例对象 来调用的方法。 直接使用 类 来调用的方法。
    @classmethod
    async def findAll(cls, where=None, args=None, **kw): # cls：表示 没有实例化的类 本身
        # find objects by where clause
        sql = [cls.__select__]

        if where: # where 限制查询条件
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('order by',None) # order by 查询结果排序
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit', None) # limit 限制sql语句查询数量， { limit [a,] n } 限制从第a个数据开始，一共返回n个数据。（a默认为0）
        if limit is not None:
            sql.append('limit')
            if isinstance(limit,int):
                sql.append('?')
                sql.append(limit)
            elif isinstance(limit,tuple) and len(limit) == 2:
                sql.append('?,?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        logging.info('修改前的sql列表：', sql)
        rs = await select(' '.join(sql), args)  # ' '.join(sql)  将 列表sql中的元素 通过 空格 练成一个字符串
        return [cls(**r) for r in rs]

    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        # find number by select and where
        sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        logging.info('修改前的sql列表：',sql)
        rs = await select(' '.join(sql), args, 1)  # ' '.join(sql)  将 列表sql中的元素 通过 空格 练成一个字符串
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    @classmethod
    async def find(cls, pk):
        # find object by primary key
        rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

# Field类
class Field(object):
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)

# Field子类
class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100'):
        super().__init__(name,ddl,primary_key,default)

class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name,'boolean', False, default)

class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name,'bigint',primary_key,default)

class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name,'real',primary_key,default)

class TextField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name,'text', False, default)