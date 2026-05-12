import os
import re
import psycopg2
import psycopg2.extras

from datetime import datetime, date

from flask import Flask, render_template, request, redirect, url_for, flash


APP_NAME = "🏠家シーシャ配合記録🏠"

TABLE_NAME = "home_shisha_mixes"

DATABASE_URL = os.environ.get("DATABASE_URL")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")


def get_conn():

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL が設定されていません。")

    return psycopg2.connect(DATABASE_URL)


def init_db():

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id SERIAL PRIMARY KEY,
            smoked_date DATE NOT NULL,
            mix_text TEXT,
            gram_detail TEXT,
            staff_name TEXT,
            rating INTEGER,
            memo TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()

    cur.close()
    conn.close()


def build_gram_detail(flavors, grams):

    lines = []

    for flavor, gram in zip(flavors, grams):

        flavor = flavor.strip()
        gram = gram.strip()

        if not flavor and not gram:
            continue

        if not flavor or not gram:
            continue

        gram = (
            gram.replace("ｇ", "")
                .replace("g", "")
                .replace("G", "")
                .strip()
        )

        try:
            gram_value = float(gram)

        except ValueError:
            continue

        if gram_value.is_integer():
            gram_text = str(int(gram_value))
        else:
            gram_text = str(gram_value)

        lines.append(f"{flavor} {gram_text}g")

    return "\n".join(lines)


def parse_gram_detail(gram_detail):

    results = []

    if not gram_detail:
        return results

    lines = gram_detail.splitlines()

    for line in lines:

        line = line.strip()

        if not line:
            continue

        line = (
            line.replace("ｇ", "g")
                .replace("Ｇ", "g")
                .replace("G", "g")
        )

        match = re.search(
            r"(.+?)\s*([0-9]+(?:\.[0-9]+)?)\s*g",
            line
        )

        if not match:
            continue

        flavor = match.group(1).strip()
        gram = float(match.group(2))

        if flavor:

            results.append({
                "flavor": flavor,
                "gram": int(gram) if gram.is_integer() else gram
            })

    return results


def save_mix(
    smoked_date,
    gram_detail,
    staff_name,
    rating,
    memo
):

    rating_value = None

    if rating:

        try:
            rating_value = int(rating)

        except ValueError:
            rating_value = None

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(f"""
        INSERT INTO {TABLE_NAME} (
            smoked_date,
            mix_text,
            gram_detail,
            staff_name,
            rating,
            memo,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s);
    """, (
        smoked_date,
        gram_detail,
        gram_detail,
        staff_name,
        rating_value,
        memo,
        datetime.now()
    ))

    conn.commit()

    cur.close()
    conn.close()


def update_mix(
    mix_id,
    smoked_date,
    gram_detail,
    staff_name,
    rating,
    memo
):

    rating_value = None

    if rating:

        try:
            rating_value = int(rating)

        except ValueError:
            rating_value = None

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(f"""
        UPDATE {TABLE_NAME}
        SET
            smoked_date = %s,
            mix_text = %s,
            gram_detail = %s,
            staff_name = %s,
            rating = %s,
            memo = %s
        WHERE id = %s;
    """, (
        smoked_date,
        gram_detail,
        gram_detail,
        staff_name,
        rating_value,
        memo,
        mix_id
    ))

    conn.commit()

    cur.close()
    conn.close()


def get_all_mixes():

    conn = get_conn()

    cur = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cur.execute(f"""
        SELECT
            id,
            smoked_date,
            mix_text,
            gram_detail,
            staff_name,
            rating,
            memo,
            created_at
        FROM {TABLE_NAME}
        ORDER BY smoked_date DESC, id DESC;
    """)

    mixes = cur.fetchall()

    cur.close()
    conn.close()

    return mixes


def get_mix_by_id(mix_id):

    conn = get_conn()

    cur = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cur.execute(f"""
        SELECT
            id,
            smoked_date,
            mix_text,
            gram_detail,
            staff_name,
            rating,
            memo,
            created_at
        FROM {TABLE_NAME}
        WHERE id = %s;
    """, (mix_id,))

    mix = cur.fetchone()

    cur.close()
    conn.close()

    return mix


@app.route("/")
def index():

    mixes = get_all_mixes()

    return render_template(
        "index.html",
        app_name=APP_NAME,
        mixes=mixes,
        active_page="history"
    )


@app.route("/add", methods=["GET", "POST"])
def add():

    today = date.today().isoformat()

    if request.method == "POST":

        smoked_date = request.form.get(
            "smoked_date",
            ""
        ).strip()

        flavors = request.form.getlist("flavor[]")
        grams = request.form.getlist("gram[]")

        staff_name = request.form.get(
            "staff_name",
            ""
        ).strip()

        rating = request.form.get(
            "rating",
            ""
        ).strip()

        memo = request.form.get(
            "memo",
            ""
        ).strip()

        if not smoked_date:

            flash("吸った日を入力してください。")

            return redirect(
                url_for("add")
            )

        gram_detail = build_gram_detail(
            flavors,
            grams
        )

        if not gram_detail:

            flash(
                "フレーバーとグラムを入力してください。"
            )

            return redirect(
                url_for("add")
            )

        save_mix(
            smoked_date=smoked_date,
            gram_detail=gram_detail,
            staff_name=staff_name,
            rating=rating,
            memo=memo
        )

        flash("配合履歴を保存しました。")

        return redirect(
            url_for("index")
        )

    return render_template(
        "add.html",
        app_name=APP_NAME,
        today=today,
        active_page="add"
    )


@app.route("/edit/<int:mix_id>", methods=["GET", "POST"])
def edit(mix_id):

    mix = get_mix_by_id(mix_id)

    if not mix:

        flash(
            "対象の履歴が見つかりませんでした。"
        )

        return redirect(
            url_for("index")
        )

    if request.method == "POST":

        smoked_date = request.form.get(
            "smoked_date",
            ""
        ).strip()

        flavors = request.form.getlist("flavor[]")
        grams = request.form.getlist("gram[]")

        staff_name = request.form.get(
            "staff_name",
            ""
        ).strip()

        rating = request.form.get(
            "rating",
            ""
        ).strip()

        memo = request.form.get(
            "memo",
            ""
        ).strip()

        if not smoked_date:

            flash("吸った日を入力してください。")

            return redirect(
                url_for("edit", mix_id=mix_id)
            )

        gram_detail = build_gram_detail(
            flavors,
            grams
        )

        if not gram_detail:

            flash(
                "フレーバーとグラムを入力してください。"
            )

            return redirect(
                url_for("edit", mix_id=mix_id)
            )

        update_mix(
            mix_id=mix_id,
            smoked_date=smoked_date,
            gram_detail=gram_detail,
            staff_name=staff_name,
            rating=rating,
            memo=memo
        )

        flash("配合履歴を更新しました。")

        return redirect(
            url_for("index")
        )

    parsed_items = parse_gram_detail(
        mix.get("gram_detail")
        or mix.get("mix_text")
        or ""
    )

    if not parsed_items:

        parsed_items = [{
            "flavor": "",
            "gram": ""
        }]

    return render_template(
        "edit.html",
        app_name=APP_NAME,
        mix=mix,
        parsed_items=parsed_items,
        active_page="history"
    )


@app.route("/search", methods=["GET"])
def search():

    search_date = request.args.get(
        "date",
        ""
    ).strip()

    search_rating = request.args.get(
        "rating",
        ""
    ).strip()

    search_staff = request.args.get(
        "staff",
        ""
    ).strip()

    mixes = []

    has_search = bool(
        search_date
        or search_rating
        or search_staff
    )

    if has_search:

        conn = get_conn()

        cur = conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        sql = f"""
            SELECT
                id,
                smoked_date,
                mix_text,
                gram_detail,
                staff_name,
                rating,
                memo,
                created_at
            FROM {TABLE_NAME}
            WHERE 1 = 1
        """

        params = []

        if search_date:

            sql += " AND smoked_date = %s"

            params.append(search_date)

        if search_rating:

            try:

                sql += " AND rating = %s"

                params.append(
                    int(search_rating)
                )

            except ValueError:
                pass

        if search_staff:

            sql += " AND staff_name ILIKE %s"

            params.append(
                f"%{search_staff}%"
            )

        sql += """
            ORDER BY
                smoked_date DESC,
                id DESC;
        """

        cur.execute(sql, params)

        mixes = cur.fetchall()

        cur.close()
        conn.close()

    return render_template(
        "search.html",
        app_name=APP_NAME,
        mixes=mixes,
        search_date=search_date,
        search_rating=search_rating,
        search_staff=search_staff,
        has_search=has_search,
        active_page="search"
    )


@app.route("/ranking")
def ranking():

    mixes = get_all_mixes()

    flavor_totals = {}

    for mix in mixes:

        gram_detail = (
            mix.get("gram_detail")
            or mix.get("mix_text")
            or ""
        )

        parsed_items = parse_gram_detail(
            gram_detail
        )

        for item in parsed_items:

            flavor = item["flavor"]

            gram = float(item["gram"])

            flavor_totals[flavor] = (
                flavor_totals.get(flavor, 0)
                + gram
            )

    rankings = sorted(
        flavor_totals.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return render_template(
        "ranking.html",
        app_name=APP_NAME,
        rankings=rankings,
        active_page="ranking"
    )


@app.route("/delete/<int:mix_id>", methods=["POST"])
def delete(mix_id):

    conn = get_conn()

    cur = conn.cursor()

    cur.execute(
        f"DELETE FROM {TABLE_NAME} WHERE id = %s;",
        (mix_id,)
    )

    conn.commit()

    cur.close()
    conn.close()

    flash("削除しました。")

    return redirect(
        url_for("index")
    )


@app.route("/manifest.json")
def manifest():

    return app.send_static_file(
        "manifest.json"
    )


@app.route("/sw.js")
def service_worker():

    return app.send_static_file(
        "sw.js"
    )


init_db()

if __name__ == "__main__":
    app.run(debug=True)