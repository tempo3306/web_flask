# encoding: utf-8
'''
@author: zhushen
@contact: 810909753@q.com
@time: 2017/5/27 16:31
'''

import psycopg2
from io import StringIO
####--------------------------------------------
####登录
conn = psycopg2.connect(dbname='hpdb',user='zs',password='6228009123')

cur = conn.cursor()
###--------------------------------------------
####删除表
# sql_delete = "DROP TABLE IF EXISTS ACCOUNT;"
# cur.execute(sql_delete)
# conn.commit()
###--------------------------------------------
####创建表
sql = """CREATE TABLE IF NOT EXISTS Account (
NAME VARCHAR(32) NOT NULL,
PASSWORD VARCHAR(32) NOT NULL,
LOGIN INT NOT NULL,
CODE VARCHAR(32) ,
MAC VARCHAR(32),
COUNT INT)
"""
try:
    cur.execute(sql)
    conn.commit()
except:
    conn.rollback()

###--------------------------------------------
#####批量增加条目
######copy_from(file, table, sep='\t', null='\\N', size=8192, columns=None)

values = []
for i in range(10,100):
    name = '123456%d' % i
    password = '123456'
    code = 'asd%d' % i
    li=[name, password, '0', code, '3']
    one='\t'.join(li)
    values.append(one)
a='\n'.join(values)

cur.copy_from(StringIO(a), 'Account',
              columns=( 'NAME', 'PASSWORD','LOGIN', 'CODE', 'COUNT'))
conn.commit()
###--------------------------------------------




try:
    cur.execute(sql)
    conn.commit()
except:
    conn.rollback()
#--------------------------------------------------------------------
#修改数据库
#更新
# passwd=1
# sql="update Account set password=100 where name='%s'" % (passwd)
# try:
#     cur.execute(sql)
#     conn.commit()
# except:
#     conn.rollback()

# #--------------------------------------------------------------------
# # 查询
# cur.execute("select * from Account")
#
# results = cur.fetchall()
# #--------------------------------------------------------------------
# print(results)

# 关闭数据库
cur.close()
conn.close()














#mysql使用
# cur.executemany('insert into Account(NAME,PASSWORD,LOGIN,CODE,COUNT) values (%s,%s,%s,%s,%s)', values)

#设置默认值
# sql="alter table tablename alter column columnname set default defaultvalue"