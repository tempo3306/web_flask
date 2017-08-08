#创建用户


#已经存在的对象就不能再创建了，通过查询，或者修改role_id    role 属性应访问 模型对象
admin_role=Role.query.filter_by(name='Manager').first()
super_role=Role.query.filter_by(name='Administrator').first()

user_role=Role.query.filter_by(name='Visitor').first()

helong=User(username="helong",role=admin_role,password='123456',passwd='123456')
yuan=User(username="yuanjunkai",role=admin_role,password='123456',passwd='123456')
zs=User(username='zs',role=super_role,password='123456',passwd='123456')
db.session.add(yuan)
db.session.add(helong)
db.session.add(zs)
db.session.commit()
for i in range(100):
    user_john = User(username='shooter%d'%i, role=user_role,password='123456',passwd='123456')
    db.session.add(user_john)
db.session.commit()

#修改

# user_role=Role(name='Inneruser')
for i in range(100):
    a=User.query.filter_by(username='shooter%d'%i).first()
    a.role_id=2    #修改ROLE_ID
    db.session.add(a)
db.session.commit()