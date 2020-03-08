import json, logging, inspect, functools

## 建立Page类来处理分页，可以在page_size更改每页项目的个数
class Page(object):
    def __init__(self, item_count, page_index=1, page_size=8):
        '''

        :param item_count: 总词条数
        :param page_index: 当前页数
        :param page_size: 每页大小
        page_count: 总页数
        offset: 相对于第一页的 偏移量 （如：第2页的偏移量为1）
        limit：
        '''
        self.item_count = item_count  # 总词条数
        self.page_size = page_size    # 分页大小
        self.page_count = item_count // page_size + (1 if item_count % page_size > 0 else 0)  # 有多少页
        if(item_count == 0) or (page_index > self.page_count):
            self.offset = 0
            self.limit = 0
            self.page_index = 1
        else:
            self.page_index = page_index
            self.offset = self.page_size * (page_index - 1)
            self.limit = self.page_size
        self.has_next = self.page_index < self.page_count
        self.has_previous = self.page_index > 1

    def __str__(self):
        return 'item_count: %s, page_count: %s, page_index: %s, page_size: %s, offset: %s, limit: %s' \
               %(self.item_count, self.page_count, self.page_index, self.page_size, self.offset, self.limit)

    __repr__ = __str__

## 以下为API的几类错误代码
class APIError(Exception):
    def __init__(self, error, data='', message=''):
        super(APIError, self).__init__(message) # 调用父类Exception的构造函数。  super(APIError, self) ：找到APIError的父类，然后将APIError的对象转化为 其父类的对象
        self.error = error
        self.data = data
        self.message = message

class APIValueError(APIError):
    def __init__(self, field, message=''):
        super(APIValueError, self).__init__('value:invalid', field, message)

class APIResourceNotFoundError(APIError):
    def __init__(self, field, message=''):
        super(APIResourceNotFoundError, self).__init__('value:notfound', field, message)

class APIPermissionError(APIError):
    def __init__(self, message=''):
        super(APIPermissionError, self).__init__('permission:forbidden', 'permission', message)

if __name__=='__main__':
    import doctest
    doctest.testmod()