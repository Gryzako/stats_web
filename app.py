from flask import Flask, render_template, request
import pandas as pd
from datetime import datetime

app = Flask(__name__)

def take_schedule():
    df = pd.read_excel('grafik.xls', sheet_name="March", usecols="A,D,E:AH")
    df.columns = df.columns.map(str)
    data = df.to_dict(orient='records')
    columns = df.columns.tolist()
    return columns, data

def load_schedule_data(hub=None):
    today_str = datetime.today().strftime("%Y-%m-%d 00:00:00")
    current_month = datetime.today().strftime("%B")

    df = pd.read_excel('grafik.xls', sheet_name=current_month)
    df.columns = df.columns.astype(str)
    # Ensure `hub` is ignored if not selected
    if hub and hub.lower() != "none":
        df = df[df['Hub'] == hub]

    shift_counts = df[today_str].value_counts().to_dict()

    return df, shift_counts, today_str

@app.route('/')
def index():
    columns, data = take_schedule()
    return render_template('index.html', columns=columns, data=data)

@app.route('/shift_stats')
def shift_stats():
    hub = request.args.get('hub')
    if hub == "None":  # Fix case where hub=None is passed in URL
        hub = None

    df, shift_counts, today_str = load_schedule_data(hub)

    selected_shift = request.args.get('shift')
    agents = []

    if selected_shift:
        agents = df[df[today_str] == selected_shift]['Agent Name'].tolist()

    return render_template(
        'shift_stats.html',
        shift_counts=shift_counts,
        hub=hub,
        agents=agents,
        selected_shift=selected_shift
    )

if __name__ == "__main__":
    app.run(debug=True)
