import json
import os
from flask import Flask, request, render_template, redirect, url_for, jsonify
import requests

app = Flask(__name__)

KEYWORDS_FILE = os.path.join(os.path.dirname(__file__), 'keywords.json')
WELCOME_CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'welcome_config.json')
ONEBOT_API = "http://localhost:3000"


def load_keywords():
    if not os.path.exists(KEYWORDS_FILE):
        return []
    with open(KEYWORDS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_keywords(keywords):
    with open(KEYWORDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(keywords, f, ensure_ascii=False, indent=2)

def load_welcome_config():
    if not os.path.exists(WELCOME_CONFIG_FILE):
        return {"enabled": False, "message": "欢迎新成员加入本群！"}
    with open(WELCOME_CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_welcome_config(config):
    with open(WELCOME_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def is_bot_admin(group_id, self_id):
    try:
        response = requests.post(f"{ONEBOT_API}/get_group_member_info", json={
            "group_id": group_id,
            "user_id": self_id
        }, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'ok' and data.get('data'):
            role = data['data'].get('role')
            return role in ['admin', 'owner']
    except requests.exceptions.RequestException as e:
        print(f"\u6743\u9650\u68c0\u67e5\u5931\u8d25: {e}")
    return False


def recall_message(message_id):
    requests.post(f"{ONEBOT_API}/delete_msg", json={"message_id": message_id})

def ban_user(group_id, user_id, duration):
    requests.post(f"{ONEBOT_API}/set_group_ban", json={
        "group_id": group_id,
        "user_id": user_id,
        "duration": duration
    })

def kick_user(group_id, user_id):
    requests.post(f"{ONEBOT_API}/set_group_kick", json={
        "group_id": group_id,
        "user_id": user_id
    })

def send_group_msg(group_id, text):
    requests.post(f"{ONEBOT_API}/send_group_msg", json={
        "group_id": group_id,
        "message": [{"type": "text", "data": {"text": text}}]
    })


@app.route('/', methods=['GET', 'POST'])
def on_event_or_keywords():
    if request.method == 'POST' and request.is_json:
        data = request.get_json()
        # 入群事件处理
        if data.get("post_type") == "notice" and data.get("notice_type") == "group_increase":
            group_id = data["group_id"]
            user_id = data["user_id"]
            welcome_config = load_welcome_config()
            if welcome_config.get("enabled") and welcome_config.get("message"):
                send_group_msg(group_id, welcome_config["message"])
            return jsonify({})
        if data.get("post_type") == "message" and data.get("message_type") == "group":
            message = "".join([seg["data"].get("text", "") for seg in data["message"] if seg["type"] == "text"])
            group_id = data["group_id"]
            user_id = data["user_id"]
            message_id = data["message_id"]
            self_id = data.get("self_id")
            keywords = load_keywords()

            for cfg in keywords:
                kw = cfg.get("keyword")
                if kw and kw in message:
                    if not is_bot_admin(group_id, self_id):
                        break

                    actions = cfg.get("action")
                    if isinstance(actions, str):
                        actions = [actions]
                    elif not isinstance(actions, list):
                        continue

                    for action in actions:
                        if action == "recall":
                            recall_message(message_id)
                        elif action == "ban":
                            ban_user(group_id, user_id, cfg.get("duration", 60))
                        elif action == "kick":
                            kick_user(group_id, user_id)
                        elif action == "reply":
                            send_group_msg(group_id, cfg.get("reply", ""))
                    break
        return jsonify({})

    # Keyword form handling
    keywords = load_keywords()
    welcome_config = load_welcome_config()
    if request.form:
        idx = request.form.get('idx', '')
        keyword = request.form.get('keyword', '').strip()
        action = request.form.getlist('action') or request.form.get('action', '').strip()
        reply = request.form.get('reply', '').strip()
        duration = request.form.get('duration', '').strip()
        delete_idx = request.form.get('delete_idx')

        if delete_idx is not None:
            try:
                delete_idx = int(delete_idx)
                if 0 <= delete_idx < len(keywords):
                    keywords.pop(delete_idx)
                    save_keywords(keywords)
            except:
                pass
            return redirect(url_for('on_event_or_keywords'))

        if isinstance(action, list) and len(action) == 1:
            action = action[0]

        new_kw = {"keyword": keyword, "action": action}

        if (isinstance(action, str) and action == 'reply') or (isinstance(action, list) and 'reply' in action):
            new_kw["reply"] = reply

        if (isinstance(action, str) and action == 'ban') or (isinstance(action, list) and 'ban' in action):
            try:
                new_kw["duration"] = int(duration)
            except:
                new_kw["duration"] = 60

        if idx == '':
            keywords.append(new_kw)
        else:
            try:
                idx = int(idx)
                keywords[idx] = new_kw
            except:
                pass
        save_keywords(keywords)
        return redirect(url_for('on_event_or_keywords'))

    return render_template('keywords.html', keywords=keywords, welcome_config=welcome_config)

@app.route('/welcome_config', methods=['POST'])
def set_welcome_config():
    message = request.form.get('welcome_message', '').strip()
    enabled = request.form.get('welcome_enabled') == '1'
    config = {"enabled": enabled, "message": message}
    save_welcome_config(config)
    return redirect(url_for('on_event_or_keywords'))


@app.route('/api/keywords', methods=['GET'])
def api_get_keywords():
    return jsonify(load_keywords())


@app.route('/keywords/saveall', methods=['POST'])
def saveall_keywords():
    data = request.get_json()
    keywords = data.get('keywords', [])
    save_keywords(keywords)
    return jsonify({'status': 'ok'})


@app.route('/delete/<int:idx>', methods=['POST'])
def delete_keyword(idx):
    keywords = load_keywords()
    if 0 <= idx < len(keywords):
        keywords.pop(idx)
        save_keywords(keywords)
    return redirect(url_for('on_event_or_keywords'))


app.static_folder = 'static'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
