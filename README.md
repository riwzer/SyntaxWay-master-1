# SyntaxWay

**SyntaxWay** – это веб-приложение на Flask, предназначенное для интерактивного изучения синтаксиса различных языков программирования. Приложение позволяет пользователям регистрироваться, выбирать язык для обучения, проходить тесты по дням, а также получать итоговую сводку результатов.

---

## Содержание

1. [Особенности проекта](#особенности-проекта)
2. [Технологии](#технологии)
3. [Установка и запуск](#установка-и-запуск)
4. [Структура проекта](#структура-проекта)
5. [Основные файлы и их назначение](#основные-файлы-и-их-назначение)
6. [Описание ключевых маршрутов (routes)](#описание-ключевых-маршрутов-routes)
7. [Как работать с приложением](#как-работать-с-приложением)

---

## Особенности проекта

- **Интерактивное обучение**: пользователь выбирает язык программирования, система автоматически генерирует обучающий материал и тесты на каждый день (от 1 до 30).
- **Пошаговые тесты**: каждый день содержит теоретический материал и тест из 15 вопросов (10 с вариантами ответов и 5 практических).
- **Отслеживание прогресса**: приложение хранит данные о каждом дне обучения, правильных/неправильных ответах и итоговых процентах.
- **Итоговая сводка**: после завершения обучения пользователь может посмотреть общую статистику, включая средний процент правильных ответов и рекомендации.
- **Сброс обучения**: пользователь может в любой момент сбросить результаты по конкретному языку и начать заново.

---

## Технологии

- **Python 3.8+**
- **Flask** – основной веб-фреймворк
- **SQLAlchemy** – ORM для работы с базой данных
- **SQLite** (по умолчанию) – может быть заменена на любую другую СУБД
- **Bootstrap 5** – стилизация фронтенда
- **Chart.js** – визуализация результатов (графики, диаграммы)
- **Marked.js** – рендеринг Markdown
- **Jinja2** – шаблонизатор, встроенный во Flask

---

## Установка и запуск

1. **Клонируйте репозиторий**:
   ```bash
   git clone https://github.com/gelios02/syntaxway.git
   cd syntaxway
   ```

2. **Создайте и активируйте виртуальное окружение** (рекомендуется):
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/Mac
   # или venv\Scripts\activate  # Windows
   ```

3. **Установите зависимости**:
   ```bash
   pip install -r requirements.txt
   ```

4**Запустите приложение**:
   ```bash
   flask run
   ```
   Приложение по умолчанию будет доступно по адресу [http://127.0.0.1:5000](http://127.0.0.1:5000).

---

## Структура проекта

Упрощённая структура каталогов :

```
syntaxway/
├── app.py                 # Точка входа (Flask-приложение)
├── models.py              # SQLAlchemy-модели (User, TrainingData, Summary и т.д.)
├── requirements.txt       # Зависимости проекта
├── templates/             # HTML-шаблоны Jinja2
│   ├── base.html
│   ├── dashboard.html
│   ├── training.html
│   ├── review.html
│   ├── summary.html
│   ├── summary_details.html
│   └── ...
├── static/                # Статические файлы (CSS, JS, изображения)
├── database/              # (опционально) Файлы миграций или сама БД SQLite
├── .env                   # (опционально) Хранение переменных окружения
```

---

## Основные файлы и их назначение

1. **`app.py`**  
   - Точка входа в Flask-приложение.  
   - Содержит регистрацию Blueprint’ов (если вы их используете), инициализацию базы данных, а также основные маршруты (`@app.route`).  
   - Имеет декораторы `login_required` для страниц, доступных только авторизованным пользователям.

2. **`models.py`**  
   - Содержит SQLAlchemy-модели:
     - `User` – данные о пользователях (логин, пароль, и т.п.).
     - `TrainingData` – хранит информацию об обучении: день, язык, материал, вопросы, результаты.
     - `Summary` – итоговая сводка по языку (средние проценты, рекомендации).

3. **`requirements.txt`**  
   - Список всех необходимых библиотек (Flask, SQLAlchemy, etc.) и их версий.

4. **`templates/`**  
   - **`base.html`** – базовый шаблон с общим оформлением (header, footer, стили).
   - **`dashboard.html`** – панель управления, выбор языка, отображение активных/завершённых обучений.
   - **`training.html`** – страница с материалом и тестовыми вопросами.
   - **`review.html`** – страница с результатами прохождения теста за день.
   - **`summary.html`** – итоговая сводка по всем языкам.
   - **`summary_details.html`** – детальные результаты по выбранному языку (дни, графики).

5. **`static/`**  
   - Каталог для статических файлов (CSS, JS, изображения).  
   - Может содержать файлы Bootstrap, Chart.js, кастомные стили, скрипты и т.д.

6. **`database/`** (необязательно)  
   - Папка для хранения миграций, файлов БД (если используете SQLite), и т.д.

---

## Описание ключевых маршрутов (routes)

- **`/dashboard`** (GET, POST)  
  - GET: отображает форму для выбора языка и список активных/завершённых обучений.  
  - POST: при выборе языка создаёт/проверяет запись в `TrainingData`, записывает язык в сессию, перенаправляет на `/training`.

- **`/training`** (GET, POST)  
  - GET: отображает материал и тестовые вопросы для текущего дня обучения.  
  - POST: сохраняет ответы, перенаправляет на `/review`.

- **`/review`** (GET)  
  - Анализирует ответы пользователя, вычисляет проценты правильных ответов, сохраняет результат в `TrainingData`.  
  - Если это день 30, создаёт запись/обновляет `Summary`.

- **`/summary`** (GET)  
  - Итоговая сводка по всем языкам: средние проценты, рекомендации.  
  - Позволяет перейти к `summary_details/<language>`.

- **`/summary_details/<language>`** (GET)  
  - Детальные результаты по выбранному языку, с графиками (Chart.js), перечислением дней и процентов.

- **`/reset_training/<language>`** (POST)  
  - Сбрасывает обучение: удаляет все записи `TrainingData` и `Summary` по указанному языку.  
  - Возвращает на `/dashboard` с сообщением о сбросе.

---

## Как работать с приложением

1. **Авторизация**:  
   - Зарегистрируйтесь или войдите (если реализована система логина).  
   - После авторизации попадёте на `/dashboard`.

2. **Выбор языка**:  
   - В форме на `dashboard.html` выберите язык (например, Python).  
   - Нажмите «Начать изучение» – создастся запись с `day=1`, и вы перейдёте на `/training`.

3. **Прохождение обучения**:  
   - На `/training` отобразится материал и тест.  
   - Ответьте на вопросы, нажмите «Сохранить ответы» – попадёте на `/review`.

4. **Результат дня**:  
   - На `/review` увидите, сколько ответов верно, рекомендации.  
   - Если день < 30, можете перейти к следующему дню.  
   - Если день = 30 – обучение завершается, и вы можете посмотреть сводку на `/summary`.

5. **Сводка обучения**:  
   - На `/summary` отображаются все языки и средние проценты правильных/неправильных ответов, рекомендации.  
   - Можете сбросить обучение, если хотите начать заново.

6. **Сброс обучения**:  
   - На странице `/dashboard` в блоке «Завершенные обучения» нажмите «Сбросить обучение» для нужного языка.  
   - Все данные по языку будут удалены.

---
