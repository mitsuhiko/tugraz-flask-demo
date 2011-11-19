from datetime import datetime
from flask import Flask, request, url_for, redirect, g, session, flash, \
     abort, render_template
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.oauth import OAuth


app = Flask(__name__)
app.config.update(
    DEBUG=True,
    SQLALCHEMY_DATABASE_URI='sqlite:///pastebin.db',
    SECRET_KEY='development-key'
)
db = SQLAlchemy(app)
oauth = OAuth()

facebook = oauth.remote_app('facebook',
    base_url='https://graph.facebook.com/',
    request_token_url=None,
    access_token_url='/oauth/access_token',
    authorize_url='https://www.facebook.com/dialog/oauth',
    consumer_key='188477911223606',
    consumer_secret='621413ddea2bcc5b2e83d42fc40495de',
    request_token_params={'scope': 'email'}
)


class Paste(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.Text)
    pub_date = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __init__(self, user, code):
        self.user = user
        self.code = code
        self.pub_date = datetime.utcnow()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    display_name = db.Column(db.String(120))
    fb_id = db.Column(db.String(30), unique=True)
    pastes = db.relationship(Paste, lazy='dynamic', backref='user')


@app.before_request
def check_user_status():
    g.user = None
    if 'user_id' in session:
        g.user = User.query.get(session['user_id'])


@app.route('/', methods=['GET', 'POST'])
def new_paste():
    if request.method == 'POST' and request.form['code']:
        paste = Paste(g.user, request.form['code'])
        db.session.add(paste)
        db.session.commit()
        return redirect(url_for('show_paste', paste_id=paste.id))
    return render_template('new_paste.html')


@app.route('/<int:paste_id>')
def show_paste(paste_id):
    paste = Paste.query.get_or_404(paste_id)
    return render_template('show_paste.html', paste=paste)


@app.route('/<int:paste_id>/delete', methods=['GET', 'POST'])
def delete_paste(paste_id):
    paste = Paste.query.get_or_404(paste_id)
    if g.user is None or g.user != paste.user:
        abort(401)
    if request.method == 'POST':
        if 'yes' in request.form:
            db.session.delete(paste)
            db.session.commit()
            flash('Paste was deleted')
            return redirect(url_for('new_paste'))
        else:
            return redirect(url_for('show_paste', paste_id=paste.id))
    return render_template('delete_paste.html', paste=paste)


@app.route('/my-pastes')
def my_pastes():
    if g.user is None:
        return redirect(url_for('login', next=request.url))
    pastes = Paste.query.filter_by(user=g.user).all()
    return render_template('my_pastes.html', pastes=pastes)


@app.route('/login')
def login():
    return facebook.authorize(callback=url_for('facebook_authorized',
        next=request.args.get('next') or request.referrer or None,
        _external=True))


@app.route('/logout')
def logout():
    session.clear()
    flash('You were logged out')
    return redirect(url_for('new_paste'))


@app.route('/login/authorized')
@facebook.authorized_handler
def facebook_authorized(resp):
    next_url = request.args.get('next') or url_for('index')
    if resp is None:
        flash('You denied the login')
        return redirect(next_url)

    session['fb_access_token'] = (resp['access_token'], '')

    me = facebook.get('/me')
    user = User.query.filter_by(fb_id=me.data['id']).first()
    if user is None:
        user = User()
        user.fb_id = me.data['id']
        db.session.add(user)

    user.display_name = me.data['name']
    db.session.commit()
    session['user_id'] = user.id

    flash('You are now logged in as %s' % user.display_name)
    return redirect(next_url)


@facebook.tokengetter
def get_facebook_oauth_token():
    return session.get('fb_access_token')


if __name__ == '__main__':
    app.run()
