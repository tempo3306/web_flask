#!/usr/bin/env python
import os
COV = None
if os.environ.get('FLASK_COVERAGE'):
    import coverage
    COV = coverage.coverage(branch=True, include='app/*')
    COV.start()

if os.path.exists('.env'):
    print('Importing environment from .env...')
    for line in open('.env'):
        var = line.strip().split('=')
        if len(var) == 2:
            os.environ[var[0]] = var[1]

from app import create_app, db
from app.models import User, Follow, Role, Permission,Auction_data,BID_action
from app.info_models import Article
from flask_script import Manager, Shell
from flask_migrate import Migrate, MigrateCommand
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin, BaseView, expose
from flask_admin.contrib.sqla import ModelView

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
manager = Manager(app)
migrate = Migrate(app, db)


def make_shell_context():
    return dict(app=app, db=db, User=User, Follow=Follow, Role=Role,
                Permission=Permission,Auction_data=Auction_data,BID_action=BID_action)
manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)


# #增加管理员界面
# admin = Admin(app, name='MyAdmin')  #, template_mode='bootstrap3'
# ###后台管理
# class MyView(BaseView):
#     @expose('/')
#     def index(self):
#         return self.render('admin/index.html')
# admin.add_view(ModelView(User, db.session))
# admin.add_view(ModelView(Role, db.session))
# admin.add_view(ModelView(Auction_data, db.session))
# admin.add_view(ModelView(BID_action, db.session))



@manager.command
def test(coverage=False):
    """Run the unit tests."""
    if coverage and not os.environ.get('FLASK_COVERAGE'):
        import sys
        os.environ['FLASK_COVERAGE'] = '1'
        os.execvp(sys.executable, [sys.executable] + sys.argv)
    import unittest
    tests = unittest.TestLoader().discover('tests')
    unittest.TextTestRunner(verbosity=2).run(tests)
    if COV:
        COV.stop()
        COV.save()
        print('Coverage Summary:')
        COV.report()
        basedir = os.path.abspath(os.path.dirname(__file__))
        covdir = os.path.join(basedir, 'tmp/coverage')
        COV.html_report(directory=covdir)
        print('HTML version: file://%s/index.html' % covdir)
        COV.erase()


@manager.command
def profile(length=25, profile_dir=None):
    """Start the application under the code profiler."""
    from werkzeug.contrib.profiler import ProfilerMiddleware
    app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[length],
                                      profile_dir=profile_dir)
    app.run()


@manager.command
def deploy():
    """Run deployment tasks."""
    from flask_migrate import upgrade
    from app.models import Role, User

    # migrate database to latest revision
    upgrade()

    # create user roles
    Role.insert_roles()

    # create self-follows for all users
    User.add_self_follows()


if __name__ == '__main__':
    manager.run()
