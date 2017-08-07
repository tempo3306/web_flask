from datetime import datetime
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from markdown import markdown
import bleach
from flask import current_app, request, url_for
from flask_login import UserMixin, AnonymousUserMixin
from app.exceptions import ValidationError
from . import db, login_manager


class Permission:
    SEARCH = 0x01
    EDIT = 0x02
#WRITE_ARTICLES = 0x04
#    MODERATE_COMMENTS = 0x08
    ADMINISTER = 0x80


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)
    users = db.relationship('User', backref='role', lazy='dynamic')

    @staticmethod
    def insert_roles():
        roles = {
            'User': (Permission.SEARCH , True),
            'Moderator': (Permission.SEARCH |
                          Permission.EDIT , False),
            'Administrator': (0xff, False)
        }
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.permissions = roles[r][0]
            role.default = roles[r][1]
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return '<Role %r>' % self.name


class Follow(db.Model):
    __tablename__ = 'follows'
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                            primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                            primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


#登录模块，用户创建
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64), unique=True, index=True)
    username = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    password_hash = db.Column(db.String(128))
    confirmed = db.Column(db.Boolean, default=False)
    name = db.Column(db.String(64))
    location = db.Column(db.String(64))
    about_me = db.Column(db.Text())
    member_since = db.Column(db.DateTime(), default=datetime.utcnow)  #创建时间
    last_seen = db.Column(db.DateTime(), default=datetime.utcnow)     #最后登录时间
    avatar_hash = db.Column(db.String(32))
#博客文章包含正文、时间戳以及和User模型之间的一对多关系
    posts = db.relationship('Post', backref='author', lazy='dynamic')

# 对应策略
    bids = db.relationship('Auction_data', backref='author', lazy='dynamic') #一对一  ,lazy='immediate',uselist=False
    actions = db.relationship('BID_action', backref='author', lazy='dynamic')   #一对一,uselist=False

    followed = db.relationship('Follow',
                               foreign_keys=[Follow.follower_id],
                               backref=db.backref('follower', lazy='joined'),
                               lazy='dynamic',
                               cascade='all, delete-orphan')
    followers = db.relationship('Follow',
                                foreign_keys=[Follow.followed_id],       #外键，用于关联
                                backref=db.backref('followed', lazy='joined'),
                                lazy='dynamic',
                                cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')    #lazy 决定了 SQLAlchemy 什么时候从数据库中加载数据

    @staticmethod
    def generate_fake(count=100):
        from sqlalchemy.exc import IntegrityError
        from random import seed
        import forgery_py

        seed()
        for i in range(count):
            u = User(email=forgery_py.internet.email_address(),
                     username=forgery_py.internet.user_name(True),
                     password=forgery_py.lorem_ipsum.word(),
                     confirmed=True,
                     name=forgery_py.name.full_name(),
                     location=forgery_py.address.city(),
                     about_me=forgery_py.lorem_ipsum.sentence(),
                     member_since=forgery_py.date.date(True))
            db.session.add(u)                        #数据库添加
            try:
                db.session.commit()                  #提交会话
            except IntegrityError:
                db.session.rollback()                #回滚到添加之前的状态



    @property            #这可以让你将一个类方法转变成一个类属性,表示只读。
    def password(self):
        raise AttributeError('password is not a readable attribute')

    #散列密码
    @password.setter    #同时有@property和@x.setter表示可读可写,@property和@x.setter和@x.deleter表示可读可写可删除
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'confirm': self.id})

    def confirm(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        return True


#判断是否有相应权限
    def can(self, permissions):
        return self.role is not None and \
            (self.role.permissions & permissions) == permissions

    def is_administrator(self):
        return self.can(Permission.ADMINISTER)

# 刷新用户最后登录时间
    def ping(self):
        self.last_seen = datetime.utcnow()   #UTC世界时间
        db.session.add(self)

###添加用户头像
    def gravatar(self, size=100, default='identicon', rating='g'):
        if request.is_secure:
            url = 'https://secure.gravatar.com/avatar'
        else:
            url = 'http://www.gravatar.com/avatar'
        hash = self.avatar_hash or hashlib.md5(
            self.username.encode('utf-8')).hexdigest()
        return '{url}/{hash}?s={size}&d={default}&r={rating}'.format(
            url=url, hash=hash, size=size, default=default, rating=rating)

#使用编码后的用户id 字段值生成一个签名令牌
    def generate_auth_token(self, expiration):
        s = Serializer(current_app.config['SECRET_KEY'],
                       expires_in=expiration)
        return s.dumps({'id': self.id}).decode('ascii')

    @staticmethod
    def verify_auth_token(token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return None
        return User.query.get(data['id'])

    def __repr__(self):
        return '<User %r>' % self.username

    #####拍牌数据库
class Auction_data(db.Model):
    __tablename__ = 'bids'
    id = db.Column(db.Integer, primary_key=True)
    IDnumber = db.Column(db.Integer)
    BIDnumber = db.Column(db.Integer)
    BIDpassword = db.Column(db.Integer)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # 对应backref
    # action_id =db.Column(db.Integer, db.ForeignKey('actions.id'))


    def __repr__(self):
        return '<Auction %r>' % self.IDnumber

    def to_json(self):
        json_post = {

            'IDnumber': self.IDnumber,
            'BIDnumber': self.BIDnumber,
            'BIDpassword': self.BIDpassword,
            'author': url_for('api.get_user', id=self.author_id,
                              _external=True),

        }
        return json_post

class BID_action(db.Model):
    __tablename__ = 'actions'
    id = db.Column(db.Integer, primary_key=True)
    diff = db.Column(db.Integer)  #参考时间差价
    refer_time = db.Column(db.Integer) #参考时间
    bid_time = db.Column(db.Integer) #出价截止时间
    delay_time = db.Column(db.Float) #出价延迟时间，0.1~0.9
    ahead_price = db.Column(db.Integer) #出价提前价格
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # auctions = db.relationship('Auction_data', backref='action', lazy='immediate') #一对一

    def __repr__(self):
        return '<BID %r>' % self.diff
'''
    def to_json(self):
        json_post = {
            'diff': self.diff,
            'refer_time': self.refer_time,
            'bid_time': self.bid_time,
            'author': url_for('api.get_user', id=self.author_id,
                              _external=True),

        }
        return json_post
'''
#继承自Flask-Login 中的AnonymousUserMixin 类，并将其设为用户未登录时current_user 的值
#这样程序不用先检查用户是否登录，就能自由调用current_user.can() 和current_user.is_administrator()
class AnonymousUser(AnonymousUserMixin):
    def can(self, permissions):
        return False

    def is_administrator(self):
        return False

login_manager.anonymous_user = AnonymousUser

#实现一个回调函数，使用指定的标识符加载用户
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#文章数据库
class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comments = db.relationship('Comment', backref='post', lazy='dynamic')
    @staticmethod
    def generate_fake(count=100):
        from random import seed, randint
        import forgery_py

        seed()
        user_count = User.query.count()
        for i in range(count):
            u = User.query.offset(randint(0, user_count - 1)).first()
            p = Post(body=forgery_py.lorem_ipsum.sentences(randint(1, 5)),
                     timestamp=forgery_py.date.date(True),
                     author=u)
            db.session.add(p)
            db.session.commit()

#转换后的博客文章HTML 代码缓存在Post 模型的一个新字段中，在模板中可以直接调用
    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
                        'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
                        'h1', 'h2', 'h3', 'p']
        target.body_html = bleach.linkify(bleach.clean(
            markdown(value, output_format='html'),
            tags=allowed_tags, strip=True))

    def to_json(self):
        json_post = {
            'url': url_for('api.get_post', id=self.id, _external=True),
            'body': self.body,
            'body_html': self.body_html,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id=self.author_id,
                              _external=True),
            'comments': url_for('api.get_post_comments', id=self.id,
                                _external=True),
            'comment_count': self.comments.count()
        }
        return json_post


    @staticmethod
    def from_json(json_post):
        body = json_post.get('body')
        if body is None or body == '':
            raise ValidationError('post does not have a body')
        return Post(body=body)

#文章的Markdown 源文本还要保存在数据库中，以防需要编辑
db.event.listen(Post.body, 'set', Post.on_changed_body)   #监听数据库

#类似
class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    disabled = db.Column(db.Boolean)

#"relationship"_id
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))     #表单名.id
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'code', 'em', 'i',
                        'strong']
        target.body_html = bleach.linkify(bleach.clean(
            markdown(value, output_format='html'),
            tags=allowed_tags, strip=True))

    def to_json(self):
        json_comment = {
            'url': url_for('api.get_comment', id=self.id, _external=True),
            'post': url_for('api.get_post', id=self.post_id, _external=True),
            'body': self.body,
            'body_html': self.body_html,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id=self.author_id,
                              _external=True),
        }
        return json_comment

    @staticmethod
    def from_json(json_comment):
        body = json_comment.get('body')
        if body is None or body == '':
            raise ValidationError('comment does not have a body')
        return Comment(body=body)

db.event.listen(Comment.body, 'set', Comment.on_changed_body)


