from flask import Flask, render_template, request, send_file, jsonify
import pandas as pd
from datetime import datetime
import io

app = Flask(__name__)

SCHEDULE_FILE_PATH = 'schedule.xlsx'

ALL_MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']

DEFAULT_SCHEDULE_COLS = ["A,C,D,E:AI", "A,C,D,E:AH", "A,C,D,E:AG", "A,C,D,E:AF"]
DEFAULT_DOWNLOAD_COLS = ["A,D,E:AI", "A,D,E:AH", "A,D,E:AG", "A,D,E:AF"]

SHIFT_NAME_MAPPING = {
    "EM_O": "EMEA Offline", "AP_O": "APAC Offline", "AM_O": "AMER Offline",
    "EM_C": "EMEA Chat", "AP_C": "APAC Chat", "AM_C": "AMER Chat",
    "EM_P": "EMEA Phone", "AP_P": "APAC Phone", "AM_P": "AMER Phone",
    "AP_W": "APAC Weekender", "EM_W": "EMEA Weekender", "AM_W": "AMER Weekender",
    "RD": "Rest Day", "PH": "Public Holiday", "EL": "Emergency Leave",
    "SL": "Sickness", "VL": "Vacation", "SP": "Special Projects",
    "KCS": "KCS Task", "KDE": "KDE Task", "ML": "Maternity Leave",
    "PL": "Paternity Leave", "BA": "Buddy Agent Task", "BD": "Blood donation",
    "M": "Meeting", "TR": "Training", "RB": "Recuperation of Bank Holiday",
    "O": "Occasional Holiday", "OS": "Child care sickness leave", "DD": "Day on Demand"
}

WORKING_DAYS = ["EM_O", "AP_O", "AM_O", "EM_C", "AP_C", "AM_C", "EM_P", "AP_P", "AM_P", "AP_W", "EM_W", "AM_W"]


def read_schedule_sheet(sheet_name, usecols_list=None):
    if usecols_list is None:
        usecols_list = DEFAULT_SCHEDULE_COLS
    for usecols in usecols_list:
        try:
            return pd.read_excel(SCHEDULE_FILE_PATH, sheet_name=sheet_name, usecols=usecols)
        except ValueError:
            continue
    return pd.DataFrame()

def take_schedule(selected_month=None):
    if selected_month is None:
        selected_month = datetime.today().strftime("%B")

    df = read_schedule_sheet(selected_month)
    if df.empty:
        df = pd.DataFrame(columns=["No data found or error reading sheet."])

    df.columns = df.columns.map(str)
    columns = df.columns.tolist()
    data = df.to_dict(orient='records')

    column_display_pairs = []
    for col in columns:
        try:
            parsed = pd.to_datetime(col, errors='coerce')
            if pd.notnull(parsed):
                display = col[8:10] + "\n" + parsed.strftime("%a")
            else:
                display = col
        except:
            display = col
        column_display_pairs.append((col, display))

    return column_display_pairs, data

def load_schedule_data(hub=None, selected_date=None):
    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
            today_str = date_obj.strftime("%Y-%m-%d 00:00:00")
            current_month = date_obj.strftime("%B")
        except ValueError:
            today_str = datetime.today().strftime("%Y-%m-%d 00:00:00")
            current_month = datetime.today().strftime("%B")
    else:
        today_str = datetime.today().strftime("%Y-%m-%d 00:00:00")
        current_month = datetime.today().strftime("%B")
    try:
        df = pd.read_excel(SCHEDULE_FILE_PATH, sheet_name=current_month)
    except Exception:
        df = pd.DataFrame(columns=['Hub', today_str])

    df.columns = df.columns.astype(str)
    if hub and hub.lower() != "none":
        df = df[df['Hub'] == hub]

    shift_counts = df[today_str].value_counts().to_dict() if today_str in df.columns else {}
    return df, shift_counts, today_str

@app.route('/')
def index():
    selected_month = request.args.get('month')
    column_display_pairs, data = take_schedule(selected_month)
    current_month = selected_month or datetime.today().strftime("%B")
    return render_template('index.html', column_display_pairs=column_display_pairs, data=data,
                           selected_month=current_month, months=ALL_MONTHS)

@app.route('/legend')
def legend():
    return render_template('legend.html')

@app.route('/shift_stats')
def shift_stats():
    hub = request.args.get('hub')
    if hub == "None":
        hub = None
    selected_date = request.args.get('date')
    df, shift_counts, today_str = load_schedule_data(hub, selected_date)
    selected_shift = request.args.get('shift')
    agents = []
    if selected_shift and today_str in df.columns:
        agents = df[df[today_str] == selected_shift]['Agent Name'].tolist()
    return render_template('shift_stats.html', shift_counts=shift_counts, hub=hub, agents=agents,
                           selected_shift=selected_shift, selected_date=selected_date, shift_names=SHIFT_NAME_MAPPING)

@app.route('/dayoff_show_summary')
def dayoff_show_summary():
    sheets = pd.read_excel(SCHEDULE_FILE_PATH, sheet_name=ALL_MONTHS)
    yearly_summary = {}
    for sheet_name in ALL_MONTHS:
        df = sheets[sheet_name]
        df["SL"] = df.iloc[:, 4:35].apply(lambda row: (row == "SL").sum(), axis=1)
        df["VL"] = df.iloc[:, 4:35].apply(lambda row: (row == "VL").sum(), axis=1)
        df["O"] = df.iloc[:, 4:35].apply(lambda row: (row == "O").sum(), axis=1)
        df["DD"] = df.iloc[:, 4:35].apply(lambda row: (row == "DD").sum(), axis=1)

        for _, row in df.iterrows():
            agent = row["Agent Name"]
            if agent not in yearly_summary:
                yearly_summary[agent] = {"SL": 0, "VL": 0, "O": 0, "DD": 0}
            yearly_summary[agent]["SL"] += row["SL"]
            yearly_summary[agent]["VL"] += row["VL"]
            yearly_summary[agent]["O"] += row["O"]
            yearly_summary[agent]["DD"] += row["DD"]

    summary_df = pd.DataFrame.from_dict(yearly_summary, orient='index').reset_index()
    summary_df.columns = ["Agent Name", "SL", "VL", "O", "DD"]
    return render_template("dayoff_show_summary.html", tables=[summary_df.to_html(classes='table table-striped', index=False)])

@app.route('/general_stats')
def general_stats():
    return render_template('general_stats.html')

@app.route('/time_cal')
def time_cal():
    return render_template('time_cal.html')

@app.route('/allocation')
def allocation():
    return render_template('allocation.html')

@app.route('/working_days')
def working_days():
    sheets = pd.read_excel(SCHEDULE_FILE_PATH, sheet_name=ALL_MONTHS)
    
    summary = {}

    for month in ALL_MONTHS:
        df = sheets[month]
        if "Agent Name" not in df.columns or "Hub" not in df.columns:
            continue

        for _, row in df.iterrows():
            agent = row["Agent Name"]
            hub = row["Hub"]
            if agent not in summary:
                summary[agent] = {"Hub": hub, **{m: 0 for m in ALL_MONTHS}}
            working_count = row.iloc[1:].isin(WORKING_DAYS).sum()
            summary[agent][month] += working_count

    summary_df = pd.DataFrame.from_dict(summary, orient="index").reset_index()
    summary_df.rename(columns={"index": "Agent Name"}, inplace=True)

    return render_template("working_days.html", table=summary_df)

@app.route('/get_availability')
def get_availability():
    selected_date = request.args.get('date')
    df, _, today_str = load_schedule_data(selected_date=selected_date)

    phone_statuses = {"AM_P", "AP_P", "EM_P"}
    chat_statuses = {"EM_C", "AP_C", "AM_C"}
    offline_statuses = {"AM_O", "AP_O", "EM_O"}
    weekender_statuses = {"AP_W", "EM_W", "AM_W"}
    special_statuses = {"SP", "TR", "BA"}
    unavailable_statuses = {"RD", "VL", "PH", "EL", "SL", "ML", "PL", "BD", "O", "OS", "DD"}

    all_statuses = phone_statuses | chat_statuses | offline_statuses | special_statuses | unavailable_statuses | weekender_statuses

    if today_str not in df.columns:
        return jsonify({hub: {"phone": 0, "chat": 0, "offline": 0, "special": 0, "unavailable": 0} for hub in ["Warsaw", "Manila", "Mexico"]})

    result = {}
    for hub in ["Warsaw", "Mexico"]:
        hub_df = df[df['Hub'].str.lower() == hub.lower()]
        shifts = hub_df[today_str].fillna("").astype(str)
        shifts = shifts[shifts.isin(all_statuses)]
        special_mask = shifts.isin(special_statuses)

        result[hub] = {
            "phone": int((shifts[~special_mask].isin(phone_statuses)).sum()),
            "chat": int((shifts[~special_mask].isin(chat_statuses)).sum()),
            "offline": int((shifts[~special_mask].isin(offline_statuses)).sum()),
            "special": int(special_mask.sum()),
            "unavailable": int((shifts[~special_mask].isin(unavailable_statuses)).sum())
        }

    # Manila split with Weekenders
    manila_df = df[df['Hub'].str.lower() == 'manila']
    manila_shifts = manila_df[today_str].fillna("").astype(str)

    region_counts = {
        'EMEA': {'phone': 0, 'chat': 0, 'offline': 0, 'weekenders': 0},
        'APAC': {'phone': 0, 'chat': 0, 'offline': 0, 'weekenders': 0},
        'AMER': {'phone': 0, 'chat': 0, 'offline': 0, 'weekenders': 0},
    }

    manila_special = 0
    manila_unavailable = 0

    for shift in manila_shifts:
        if shift in phone_statuses:
            if shift == 'EM_P': region_counts['EMEA']['phone'] += 1
            elif shift == 'AP_P': region_counts['APAC']['phone'] += 1
            elif shift == 'AM_P': region_counts['AMER']['phone'] += 1
        elif shift in chat_statuses:
            if shift == 'EM_C': region_counts['EMEA']['chat'] += 1
            elif shift == 'AP_C': region_counts['APAC']['chat'] += 1
            elif shift == 'AM_C': region_counts['AMER']['chat'] += 1
        elif shift in offline_statuses:
            if shift == 'EM_O': region_counts['EMEA']['offline'] += 1
            elif shift == 'AP_O': region_counts['APAC']['offline'] += 1
            elif shift == 'AM_O': region_counts['AMER']['offline'] += 1
        elif shift in weekender_statuses:
            if shift == 'EM_W': region_counts['EMEA']['weekenders'] += 1
            elif shift == 'AP_W': region_counts['APAC']['weekenders'] += 1
            elif shift == 'AM_W': region_counts['AMER']['weekenders'] += 1
        elif shift in special_statuses:
            manila_special += 1
        elif shift in unavailable_statuses:
            manila_unavailable += 1

    result['Manila'] = region_counts
    result['ManilaSpecial'] = manila_special
    result['ManilaUnavailable'] = manila_unavailable

    return jsonify(result)

@app.route('/manila_ho')
def manila_ho():
    try:
        df = pd.read_excel(SCHEDULE_FILE_PATH, sheet_name='ManilaHO')
    except Exception as e:
        df = pd.DataFrame({'Error': [str(e)]})
    
    return render_template("manila_ho.html", table=df)


@app.route('/download_schedule')
def download_schedule():
    selected_month = request.args.get('month') or datetime.today().strftime("%B")
    df = read_schedule_sheet(selected_month, usecols_list=DEFAULT_DOWNLOAD_COLS)

    output = io.StringIO()
    df.to_csv(output, index=False, sep=';')
    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'schedule_{selected_month}.csv'
    )

if __name__ == "__main__":
    app.run(debug=True)