from flask import Flask, render_template, request
import sqlite3
from datetime import datetime

app = Flask(__name__)
DATABASE = 'db.sqlite'

"""
CREATE TABLE st_stihi (
    st_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    st_compilation INTEGER NOT NULL,
    st_date TEXT NOT NULL,
    st_title TEXT NOT NULL,
    st_text TEXT NOT NULL,
    st_notes TEXT DEFAULT ''
);
"""

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def sanitize_text(text):
    """Sanitize text fields by replacing escaped characters with their original forms."""
    if text is None:
        return None
    text = text.replace('\\"', '"')
    text = text.replace('\\n', '\n')
    return text

@app.route('/', methods=['GET', 'POST'])
def index():
    query = request.form.get('query')
    target = request.form.get('target', 'all')
    comp = request.form.get('comp')
    year = request.form.get('year')
    articles = []

    conn = get_db_connection()

    # Get totals, last compilation, and available years
    total = conn.execute("SELECT COUNT(*) FROM st_stihi").fetchone()[0]
    last_comp = conn.execute("SELECT MAX(st_compilation) FROM st_stihi").fetchone()[0]
    years = [row[0] for row in conn.execute("SELECT DISTINCT strftime('%Y', st_date) FROM st_stihi WHERE st_date != '0000-00-00'").fetchall()]

    # Query construction
    query_condition = []
    params = []

    if query:
        if target == 'title':
            query_condition.append("st_title LIKE ?")
            params.append(f"%{query}%")
        else:
            query_condition.append("(st_title LIKE ? OR st_text LIKE ? OR st_notes LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

    if comp:
        query_condition.append("st_compilation = ?")
        params.append(comp)

    if year:
        if year == "2000":
            query_condition.append("st_date = '0000-00-00'")
        else:
            query_condition.append("strftime('%Y', st_date) = ?")
            params.append(year)

    query_string = " AND ".join(query_condition)
    if query_string:
        articles = conn.execute(
            f"SELECT st_ID, st_date, st_compilation, st_title FROM st_stihi WHERE {query_string}",
            params
        ).fetchall()
    else:
        articles = conn.execute(
            "SELECT st_ID, st_date, st_compilation, st_title FROM st_stihi"
        ).fetchall()

    conn.close()

    # Sanitize titles
    articles = [
        {
            **dict(article),
            'st_date': (
                datetime.strptime(article['st_date'], '%Y-%m-%d').strftime('%d. %m. %Y')
                if article['st_date'] and article['st_date'] != '0000-00-00'
                else 'Дата неизвестна'
            ),
            'st_title': sanitize_text(article['st_title'])
        }
        for article in articles
    ]

    return render_template(
        'index.html',
        articles=articles,
        query=query,
        target=target,
        comp=comp,
        year=year,
        total=total,
        last_comp=last_comp,
        years=years,
    )

@app.route('/duplicates')
def duplicates():
    conn = get_db_connection()

    duplicates = conn.execute(
        """
        SELECT s1.st_ID, s1.st_title, s1.st_compilation, s1.st_date
        FROM st_stihi s1
        INNER JOIN (
            SELECT st_title
            FROM st_stihi
            GROUP BY st_title
            HAVING COUNT(st_ID) > 1
        ) s2 ON s1.st_title = s2.st_title
        ORDER BY s1.st_title
        """
    ).fetchall()

    last_comp = conn.execute("SELECT MAX(st_compilation) FROM st_stihi").fetchone()[0]
    conn.close()

    duplicates = [
        {
            **dict(duplicate),
            'st_date': (
                datetime.strptime(duplicate['st_date'], '%Y-%m-%d').strftime('%d. %m. %Y')
                if duplicate['st_date'] and duplicate['st_date'] != '0000-00-00'
                else 'Дата неизвестна'
            ),
            'st_title': sanitize_text(duplicate['st_title']),
        }
        for duplicate in duplicates
    ]

    return render_template('duplicates.html', duplicates=duplicates, last_comp=last_comp)


@app.route('/article/<int:article_id>')
def article(article_id):
    conn = get_db_connection()
    # Fetch the article details
    article = conn.execute(
        "SELECT * FROM st_stihi WHERE st_ID = ?",
        (article_id,)
    ).fetchone()
    
    # Fetch the last compilation number
    last_comp = conn.execute("SELECT MAX(st_compilation) FROM st_stihi").fetchone()[0]
    conn.close()

    if article is None:
        return "Article not found", 404

    # Format date and sanitize fields
    article = {
        key: sanitize_text(value) if isinstance(value, str) else value
        for key, value in dict(article).items()
    }
    if article['st_date'] and article['st_date'] != '0000-00-00':
        article['st_date'] = datetime.strptime(article['st_date'], '%Y-%m-%d').strftime('%d. %m. %Y')
    else:
        article['st_date'] = 'Дата неизвестна'

    return render_template('article.html', article=article, last_comp=last_comp)


if __name__ == '__main__':
    app.run(debug=True)