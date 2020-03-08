import conf.config_default

class Dict(dict):
    '''
    Simple dict but support access as x.y style
    '''

    def __init__(self, names=(), values=(), **kw):
        super(Dict,self).__init__(**kw)
        for k, v in zip(names, values): # zip(iterable,...) 用于将可迭代对象打包成一个个元组 （如：zip(names,values)将 names(n1,n2,...)和values(v1,v2,...)转换为
                                        # [(n1,v1),(n2,v2),.....]
            self[k] = v

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

def merge(defaults, override):
    '''
    将 defaults中的配置文件用 override的配置文件覆盖。
    :param defaults:
    :param override:
    :return:
    '''
    r = {} # 新产生的配置
    for k, v in defaults.items():
        if k in override:
            if isinstance(v, dict):
                r[k] = merge(v, override[k])
            else:
                r[k] = override[k]
        else:
            r[k] = v
    return r

def toDict(d):
    D = Dict()
    for k,v in d.items():
        D[k] = toDict(v) if isinstance(v, dict) else v # 递归将多层 dict 都转化为 Dict
    return D

configs = conf.config_default.configs

try:
    import conf.config_override
    configs = merge(configs, conf.config_override.configs)
except ImportError:
    pass

configs = toDict(configs)