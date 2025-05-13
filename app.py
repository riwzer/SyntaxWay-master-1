from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import os
import re
import json
import time
import markdown
from dotenv import load_dotenv
from datetime import timedelta
from functools import wraps
from sqlalchemy import text
from AI import *

# Загрузка переменных окружения
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "default_secret")
DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///site.db")

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

@app.template_filter("fromjson")
def fromjson(value):
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return {}

app.jinja_env.filters["fromjson"] = fromjson
# Декоратор для защиты маршрутов
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Пожалуйста, войдите в систему.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


# Модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    # Связи с данными обучения и итоговой сводкой
    trainings = db.relationship('TrainingData', backref='user', lazy=True)
    summaries = db.relationship('Summary', backref='user', lazy=True)


# Модель дневных данных обучения
class TrainingData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    day = db.Column(db.Integer, nullable=False)
    language = db.Column(db.String(50))
    material = db.Column(db.Text)
    questions = db.Column(db.Text)
    answers = db.Column(db.Text)
    recommendation = db.Column(db.Text)
    correct_percentage = db.Column(db.Float)
    incorrect_percentage = db.Column(db.Float)


# Модель итоговой сводки
class Summary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    summary = db.Column(db.Text)
    overall_correct_percentage = db.Column(db.Float)
    overall_incorrect_percentage = db.Column(db.Float)
    language = db.Column(db.String(50))
    day = db.Column(db.Integer)


with app.app_context():
    db.create_all()


# Лендинг-страница (доступна всем)
@app.route("/")
def landing():
    return render_template("landing.html")


# Страница регистрации
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
        # Проверяем наличие пользователя с таким же именем или email
        user = User.query.filter((User.username == username) | (User.email == email)).first()
        if user:
            flash("Пользователь с таким именем или email уже существует.", "danger")
            return redirect(url_for("register"))
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash("Аккаунт успешно создан! Теперь вы можете войти.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


# Страница логина
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            session["user_id"] = user.id
            session.permanent = True
            flash("Вы успешно вошли в систему!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Неверный email или пароль.", "danger")
    return render_template("login.html")



@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("login"))


@app.route("/set_language", methods=["POST"])
@login_required
def set_language():
    data = request.get_json()
    session["selected_language"] = data["language"]
    return jsonify(success=True)

# Панель управления (только для авторизованных)
@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    user_id = session["user_id"]
    user = User.query.get(user_id)

    if request.method == "POST":
        selected_language = request.form.get("language")
        if not selected_language:
            flash("Пожалуйста, выберите язык для изучения.", "warning")
            return redirect(url_for("dashboard"))

        # Сбрасываем старый язык в сессии и пишем новый
        session.pop("selected_language", None)
        session["selected_language"] = selected_language

        # Проверяем, есть ли запись о TrainingData
        existing_training = TrainingData.query.filter_by(user_id=user_id, language=selected_language).first()
        if not existing_training:
            # Создаем новую запись, начиная с day=1
            new_training = TrainingData(
                user_id=user_id,
                day=1,
                language=selected_language,
                material=None,
                questions=None,
                answers=None,
                correct_percentage=None,
                incorrect_percentage=None
            )
            db.session.add(new_training)
            db.session.commit()
            flash(f"Выбран язык: {selected_language}. Запись создана, начинаем обучение!", "success")
        else:
            flash(f"Вы уже изучаете {selected_language}. Продолжаем обучение!", "info")

        return redirect(url_for("training"))

    # Собираем все языки, у которых есть TrainingData в диапазоне 1..30
    languages = db.session.query(TrainingData.language)\
        .filter(TrainingData.user_id == user_id, TrainingData.day.between(1, 30))\
        .distinct().all()
    languages = [l[0] for l in languages]

    # Разделяем на незавершённые и завершённые
    active_languages = {}
    completed_languages = {}

    for lang in languages:
        # Находим последнюю запись по дню
        last_record = TrainingData.query.filter_by(user_id=user_id, language=lang)\
            .order_by(TrainingData.day.desc()).first()
        if not last_record:
            continue

        # Если день < 30 ИЛИ correct_percentage is None => обучение не завершено
        if last_record.day < 30 or last_record.correct_percentage is None:
            active_languages[lang] = last_record.day
        else:
            # Иначе считаем обучение завершённым
            completed_languages[lang] = last_record.day

    popular_languages = ["Python", "JavaScript", "Java", "C++", "Ruby"]

    return render_template(
        "dashboard.html",
        user=user,
        popular_languages=popular_languages,
        active_languages=active_languages,
        completed_languages=completed_languages
    )


@app.route("/reset_training/<language>", methods=["POST"])
@login_required
def reset_training(language):
    user_id = session["user_id"]
    # Удаляем все записи из TrainingData и Summary
    TrainingData.query.filter_by(user_id=user_id, language=language).delete()
    Summary.query.filter_by(user_id=user_id, language=language).delete()
    db.session.commit()

    # Очищаем sessionStorage на клиенте
    flash(f"Обучение по {language} было сброшено.", "danger")
    return redirect(url_for("dashboard"))


# Маршрут для страницы обучения
@app.route("/training", methods=["GET", "POST"])
@login_required
def training():
    if request.method == "POST":
        # Собираем ответы из формы
        answers = {}
        for i in range(1, 16):
            answer = request.form.get(f"answer_{i}")
            answers[str(i)] = answer

        user = User.query.get(session["user_id"])
        selected_language = session.get("selected_language")
        # Получаем последнюю запись по выбранному языку
        current_training = TrainingData.query.filter_by(
            user_id=user.id, language=selected_language
        ).order_by(TrainingData.day.desc()).first()

        # Извлекаем текст вопросов из записи (предполагаем, что вопросы разделены двойным переносом строки)
        question_blocks = re.split(r"\n\s*\n", current_training.questions.strip())
        questions_dict = {}
        for i, block in enumerate(question_blocks, start=1):
            # Для каждого блока берем первую строку, которая содержит текст вопроса
            lines = block.splitlines()
            if lines:
                questions_dict[str(i)] = lines[0].strip()

        # Комбинируем вопросы и ответы в один словарь
        combined = {}
        for q_num, answer in answers.items():
            question_text = questions_dict.get(q_num, "")
            combined[q_num] = {"question": question_text, "answer": answer}

        # Сохраняем комбинированные данные в поле answers записи TrainingData
        current_training.answers = json.dumps(combined, ensure_ascii=False)
        db.session.commit()
        session["submitted_answers"] = combined
        flash("Ваши ответы сохранены!", "success")
        return redirect(url_for("review"))

    return render_template("training.html", selected_language=session.get("selected_language"))


@app.route("/generate_training", methods=["GET"])
@login_required
def generate_training():
    user = User.query.get(session["user_id"])
    selected_language = session.get("selected_language")
    if not selected_language:
        return jsonify({"error": "Язык не выбран"}), 400

    # Получаем последнюю запись по данному пользователю и языку
    latest_training = TrainingData.query.filter_by(
        user_id=user.id, language=selected_language
    ).order_by(TrainingData.day.desc()).first()

    # Если день 0 найден, пропускаем его и начинаем с 1
    if latest_training and latest_training.day == 0:
        current_day = 1
    elif latest_training:
        # Если последний день завершён (есть correct_percentage), переходим к следующему дню
        if latest_training.correct_percentage is not None:
            current_day = latest_training.day + 1
        else:
            # Если материал и вопросы есть, просто возвращаем существующую запись
            if latest_training.material and latest_training.questions:
                return jsonify({
                    "day": latest_training.day,
                    "material": latest_training.material,
                    "questions": latest_training.questions
                })
            # Иначе продолжаем с тем же днём, но с генерацией материалов
            current_day = latest_training.day
    else:
        # Если записей нет, начинаем с 1 дня
        current_day = 1

    # Ограничиваем диапазон дней от 1 до 30
    if current_day > 30:
        return jsonify({"error": "Вы завершили обучение для этого языка"}), 400

    # Если 30-й день уже есть и материалы заполнены, возвращаем их
    if current_day == 30:
        existing_day30 = TrainingData.query.filter_by(
            user_id=user.id, language=selected_language, day=30
        ).first()
        if existing_day30 and existing_day30.material and existing_day30.questions:
            return jsonify({
                "day": existing_day30.day,
                "material": existing_day30.material,
                "questions": existing_day30.questions
            })

    # Проверяем, есть ли запись для текущего дня с материалами и вопросами
    existing_training = TrainingData.query.filter_by(
        user_id=user.id, language=selected_language, day=current_day
    ).first()

    if existing_training and existing_training.material and existing_training.questions:
        # Если запись есть и материалы уже заполнены, просто возвращаем их
        return jsonify({
            "day": existing_training.day,
            "material": existing_training.material,
            "questions": existing_training.questions
        })
    else:
        # Генерируем новый материал и вопросы для текущего дня
        material = generate_material(selected_language, current_day)
        material = re.sub(r"^День\s*\d+\s*:\s*", "", material, flags=re.IGNORECASE)
        questions = generate_questions(selected_language, material, current_day)
        questions = clean_questions_text(questions)

        if existing_training:
            # Если запись уже была, просто обновляем её
            existing_training.material = material
            existing_training.questions = questions
        else:
            # Если записи нет, создаём новую
            new_training = TrainingData(
                user_id=user.id,
                day=current_day,
                language=selected_language,
                material=material,
                questions=questions,
                answers=None,
                correct_percentage=None,
                incorrect_percentage=None,
                recommendation=None
            )
            db.session.add(new_training)

        db.session.commit()

        return jsonify({
            "day": current_day,
            "material": material,
            "questions": questions
        })


@app.route("/retake_test", methods=["POST"])
@login_required
def retake_test():
    """
    Сбрасывает результаты (recommendation, correct_percentage, incorrect_percentage)
    и возвращает пользователя на /training для пересдачи теста.
    """
    user_id = session["user_id"]
    selected_language = session.get("selected_language")
    record = TrainingData.query.filter_by(
        user_id=user_id, language=selected_language
    ).order_by(TrainingData.day.desc()).first()
    if record:
        record.correct_percentage = None
        record.incorrect_percentage = None
        record.recommendation = None
        db.session.commit()
        flash("Результаты сброшены. Пройдите тест ещё раз.", "info")
    return redirect(url_for("training"))


@app.route("/next_day", methods=["POST"])
@login_required
def next_day():
    user_id = session["user_id"]
    selected_language = session.get("selected_language")
    record = TrainingData.query.filter_by(user_id=user_id, language=selected_language).order_by(
        TrainingData.day.desc()).first()
    if not record:
        flash("Нет данных для обучения", "warning")
        return redirect(url_for("dashboard"))

    current_day = record.day
    if current_day >= 30:
        # Если это 30-й день, агрегируем данные и записываем Summary
        records = TrainingData.query.filter_by(user_id=user_id, language=selected_language).all()
        valid_records = [r for r in records if r.correct_percentage is not None]
        if valid_records:
            overall_correct = sum(r.correct_percentage for r in valid_records) / len(valid_records)
            overall_incorrect = sum(r.incorrect_percentage for r in valid_records) / len(valid_records)
        else:
            overall_correct = 0
            overall_incorrect = 0
        summary_text = f"Поздравляем! Это был последний день обучения. Ваш средний процент правильных ответов: {overall_correct:.2f}%."
        new_summary = Summary(
            user_id=user_id,
            summary=summary_text,
            overall_correct_percentage=overall_correct,
            overall_incorrect_percentage=overall_incorrect,
            language=selected_language,
            day=30
        )
        db.session.add(new_summary)
        db.session.commit()
        flash("Вы завершили обучение! Просмотрите результаты обучения.", "success")
        return redirect(url_for("dashboard"))
    else:
        # Если текущий день завершен (record.correct_percentage != None), переходим к следующему дню
        next_day = current_day + 1
        if next_day > 30:
            flash("Вы завершили обучение для этого языка.", "info")
            return redirect(url_for("dashboard"))
        return redirect(url_for("training"))


@app.route("/review_data", methods=["GET"])
@login_required
def review_data():
    user_id = session["user_id"]
    selected_language = session.get("selected_language")

    training_record = TrainingData.query.filter_by(
        user_id=user_id, language=selected_language
    ).order_by(TrainingData.day.desc()).first()

    if not training_record or not training_record.answers:
        return jsonify({"error": "Нет данных для оценки"}), 400

    # Если результаты уже оценены, используем их
    if training_record.correct_percentage is not None and training_record.recommendation:
        correct = training_record.correct_percentage
        recommendation = training_record.recommendation
    else:
        answers_json = training_record.answers
        answers_dict = json.loads(answers_json)
        evaluation_input = ""
        for q_num, qa in answers_dict.items():
            evaluation_input += f"Вопрос {q_num}: {qa['question']} Ответ: {qa['answer']}\n"
        evaluation_input = evaluation_input.strip()

        # Анализируем ответы через нейросеть
        evaluation_response = evaluate_answers(selected_language, evaluation_input)
        correct_match = re.search(r"Количество правильных:\s*(\d+)\s*из\s*15", evaluation_response)
        correct_count = int(correct_match.group(1)) if correct_match else 0
        correct = (correct_count / 15) * 100
        rec_match = re.search(r"Рекомендации:\s*(.*)", evaluation_response, flags=re.DOTALL)
        recommendation = rec_match.group(1).strip() if rec_match else "Нет рекомендаций"

        training_record.correct_percentage = correct
        training_record.incorrect_percentage = 100 - correct
        training_record.recommendation = recommendation
        db.session.commit()

    last_day = (training_record.day == 30)

    # Если это 30-й день, вычисляем средние значения по всем дням
    if last_day:
        records = TrainingData.query.filter_by(user_id=user_id, language=selected_language).all()
        valid_records = [r for r in records if r.correct_percentage is not None and str(r.correct_percentage).strip()]

        if valid_records:
            avg_correct = sum(float(r.correct_percentage or 0) for r in valid_records) / len(valid_records)
            avg_incorrect = sum(float(r.incorrect_percentage or 0) for r in valid_records) / len(valid_records)
        else:
            avg_correct = 0
            avg_incorrect = 0

        # Вызов функции evaluate_result для получения итогового summary
        summary_text = evaluate_result(selected_language, avg_correct, avg_incorrect)

        # Обновляем или создаем запись в таблице Summary
        summary_record = Summary.query.filter_by(user_id=user_id, language=selected_language, day=30).first()
        if summary_record:
            summary_record.overall_correct_percentage = avg_correct
            summary_record.overall_incorrect_percentage = avg_incorrect
            summary_record.summary = summary_text
        else:
            summary_record = Summary(
                user_id=user_id,
                language=selected_language,
                day=30,
                overall_correct_percentage=avg_correct,
                overall_incorrect_percentage=avg_incorrect,
                summary=summary_text
            )
            db.session.add(summary_record)

        db.session.commit()

    return jsonify({
        "correct_percentage": correct,
        "incorrect_percentage": 100 - correct,
        "recommendation": recommendation,
        "day": training_record.day,
        "last_day": last_day
    })


@app.route("/review", methods=["GET"])
@login_required
def review():
    return render_template("review.html")


@app.route("/summary")
@login_required
def summary():
    user_id = session["user_id"]

    # Получаем все записи по обучению, исключая день 0
    summary_records = Summary.query.filter(Summary.user_id == user_id, Summary.day != 0).all()

    # Словарь для хранения агрегированных данных по языкам
    summary_data = {}

    for record in summary_records:
        language = record.language
        training_data = TrainingData.query.filter_by(user_id=user_id, language=language).order_by(
            TrainingData.day.asc()).all()

        # Преобразуем correct_percentage и incorrect_percentage в числа
        total_days = len(training_data)
        total_correct = sum(
            float(r.correct_percentage) for r in training_data if r.correct_percentage not in [None, ""])
        total_incorrect = sum(
            float(r.incorrect_percentage) for r in training_data if r.incorrect_percentage not in [None, ""])

        avg_correct = round(total_correct / total_days, 2) if total_days else 0
        avg_incorrect = round(total_incorrect / total_days, 2) if total_days else 0

        # Обработка Markdown для рекомендаций
        recommendations = markdown.markdown(record.summary if record.summary else "Нет рекомендаций")

        summary_data[language] = {
            "correct_avg": avg_correct,
            "incorrect_avg": avg_incorrect,
            "recommendations": recommendations
        }

    return render_template("summary.html", summary_data=summary_data)

@app.route("/summary_details/<language>")
@login_required
def summary_details(language):
    user_id = session["user_id"]

    # Получаем все дни обучения для выбранного языка
    training_data = TrainingData.query.filter_by(user_id=user_id, language=language).order_by(
        TrainingData.day.asc()).all()

    return render_template("summary_details.html", language=language, training_data=training_data)


@app.route("/daysdata")
@login_required
def daysdata():
    user_id = session["user_id"]

    # Получаем список всех языков, по которым есть записи
    languages = db.session.query(TrainingData.language).filter_by(user_id=user_id).distinct().all()
    language_list = [lang[0] for lang in languages]

    detailed_data = {}
    for lang in language_list:
        records = TrainingData.query.filter_by(user_id=user_id, language=lang).order_by(TrainingData.day.asc()).all()

        formatted_records = []
        for record in records:
            try:
                parsed_answers = json.loads(record.answers) if record.answers and record.answers.strip() else {}
            except json.JSONDecodeError:
                parsed_answers = {}

            formatted_record = {
                "day": record.day,
                "language": record.language,
                "material": markdown.markdown(record.material) if record.material else "<p>Нет материала</p>",
                "answers": parsed_answers,  # Исправлено
                "correct_percentage": record.correct_percentage,
                "incorrect_percentage": record.incorrect_percentage,
            }
            formatted_records.append(formatted_record)

        detailed_data[lang] = formatted_records

    return render_template("daysdata.html", detailed_data=detailed_data)

if __name__ == "__main__":

    app.run(debug=True)
