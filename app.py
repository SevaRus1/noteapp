from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey2026'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///notes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# создаём папку для картинок если её нет
if not os.path.exists('static/uploads'):
    os.makedirs('static/uploads')


# ========== БАЗА ДАННЫХ (ORM модели) ==========

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    notes = db.relationship('Note', backref='author', lazy=True)


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200))
    date = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(50), default='общее')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


# создаём таблицы (один раз при запуске)
with app.app_context():
    db.create_all()


# ========== МАРШРУТЫ ==========

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm = request.form['confirm_password']

        # проверка длины логина
        if len(username) < 3:
            flash('Имя пользователя должно быть минимум 3 символа!', 'danger')
            return redirect(url_for('register'))
        if len(username) > 20:
            flash('Имя пользователя не может быть длиннее 20 символов!', 'danger')
            return redirect(url_for('register'))

        if password != confirm:
            flash('Пароли не совпадают!', 'danger')
            return redirect(url_for('register'))

        # проверяем есть ли уже такой пользователь
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Пользователь уже существует!', 'danger')
            return redirect(url_for('register'))

        # создаём нового пользователя
        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()

        flash('Регистрация успешна! Войдите в систему.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Добро пожаловать, {username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверные логин или пароль!', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_notes = Note.query.filter_by(user_id=session['user_id']).order_by(Note.id.desc()).all()
    return render_template('dashboard.html', notes=user_notes, username=session['username'])


@app.route('/add_note', methods=['GET', 'POST'])
def add_note():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category = request.form.get('category', 'общее')

        # обрабатываем картинку
        image_file = request.files.get('image')
        filename = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            name, ext = os.path.splitext(filename)
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}{ext}"
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        # создаём заметку в базе данных
        note = Note(
            title=title,
            content=content,
            image=filename,
            date=(datetime.now() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M'),
            category=category,
            user_id=session['user_id']
        )
        db.session.add(note)
        db.session.commit()

        flash('Заметка добавлена!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_note.html')


@app.route('/edit_note/<int:note_id>', methods=['GET', 'POST'])
def edit_note(note_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    note = Note.query.filter_by(id=note_id, user_id=session['user_id']).first()
    if not note:
        flash('Заметка не найдена!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        note.title = request.form['title']
        note.content = request.form['content']
        note.category = request.form.get('category', 'общее')

        image_file = request.files.get('image')
        if image_file and image_file.filename:
            if note.image:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], note.image)
                if os.path.exists(old_path):
                    os.remove(old_path)

            filename = secure_filename(image_file.filename)
            name, ext = os.path.splitext(filename)
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}{ext}"
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            note.image = filename

        db.session.commit()
        flash('Заметка обновлена!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('edit_note.html', note=note)


@app.route('/delete_note/<int:note_id>')
def delete_note(note_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    note = Note.query.filter_by(id=note_id, user_id=session['user_id']).first()
    if note:
        if note.image:
            img_path = os.path.join(app.config['UPLOAD_FOLDER'], note.image)
            if os.path.exists(img_path):
                os.remove(img_path)
        db.session.delete(note)
        db.session.commit()
        flash('Заметка удалена!', 'success')

    return redirect(url_for('dashboard'))


@app.route('/search')
def search():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    query = request.args.get('q', '').lower()

    if query:
        notes = Note.query.filter(
            Note.user_id == session['user_id'],
            (Note.title.contains(query) | Note.content.contains(query))
        ).all()
    else:
        notes = Note.query.filter_by(user_id=session['user_id']).all()

    return render_template('dashboard.html', notes=notes, search_query=query)


@app.route('/category/<category>')
def filter_category(category):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if category == 'все':
        notes = Note.query.filter_by(user_id=session['user_id']).all()
    else:
        notes = Note.query.filter_by(user_id=session['user_id'], category=category).all()

    return render_template('dashboard.html', notes=notes, current_category=category)


# ========== REST API ==========

@app.route('/api/notes')
def api_get_notes():
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    notes = Note.query.filter_by(user_id=session['user_id']).all()
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'content': n.content,
        'image': n.image,
        'date': n.date,
        'category': n.category
    } for n in notes])


@app.route('/api/notes/<int:note_id>', methods=['GET'])
def api_get_note(note_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    note = Note.query.filter_by(id=note_id, user_id=session['user_id']).first()
    if note:
        return jsonify({
            'id': note.id,
            'title': note.title,
            'content': note.content,
            'image': note.image,
            'date': note.date,
            'category': note.category
        })
    return jsonify({'error': 'Заметка не найдена'}), 404


@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
def api_delete_note(note_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    note = Note.query.filter_by(id=note_id, user_id=session['user_id']).first()
    if note:
        db.session.delete(note)
        db.session.commit()
        return jsonify({'message': 'Заметка удалена'})
    return jsonify({'error': 'Заметка не найдена'}), 404


@app.route('/api/stats')
def api_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401

    notes = Note.query.filter_by(user_id=session['user_id']).all()
    categories = {}
    for note in notes:
        categories[note.category] = categories.get(note.category, 0) + 1

    return jsonify({
        'total': len(notes),
        'categories': categories,
        'user': session['username']
    })


with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', email='admin@example.com', password='admin123')
        db.session.add(admin)
        db.session.commit()
        print('Тестовый аккаунт создан: admin / admin123')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
