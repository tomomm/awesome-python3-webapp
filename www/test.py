import www.orm as orm
import asyncio
from www.models import User,Blog,Comment

async def test(loop):
    await orm.create_pool(loop=loop, user='root', password='123456', db='awesome')
    u = User(name='Test', email='test@qq.com', passwd='123456', image='about:blank')
    await u.save()
    ##
    orm.__pool.close()
    await orm.__pool.wait_closed()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test(loop))
    loop.close()

