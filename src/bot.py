import json
import os
from flask import Flask, request, render_template, redirect, url_for, jsonify
import requests

app = Flask(__name__)

KEYWORDS_FILE = os.path.join(os.path.dirname(__file__), 'keywords.json')
ONEBOT_API = "http://localhost:3000"


def load_keywords():
    if not os.path.exists(KEYWORDS_FILE):
        return []
    with open(KEYWORDS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_keywords(keywords):
    with open(KEYWORDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(keywords, f, ensure_ascii=False, indent=2)


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
        if data.get("post_type") == "message" and data.get("message_type") == "group":
            message = "".join([seg["data"].get("text", "") for seg in data["message"] if seg["type"] == "text"])
            group_id = data["group_id"]
            user_id = data["user_id"]
            message_id = data["message_id"]
            self_id = data.get("self_id")

            print(f"\u6536\u5230\u6d88\u606f: {message} (\u7fa4:{group_id}, \u7528\u6237:{user_id}, \u6d88\u606fID:{message_id})")
            keywords = load_keywords()

            for cfg in keywords:
                kw = cfg.get("keyword")
                if kw and kw in message:
                    if not is_bot_admin(group_id, self_id):
                        print(f"\u68c0\u6d4b\u5230\u5173\u952e\u8bcd '{kw}'\uff0c\u4f46\u673a\u5668\u4eba\u975e\u7ba1\u7406\u5458\uff0c\u8df3\u8fc7\u64cd\u4f5c\u3002")
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

    return render_template('keywords.html', keywords=keywords)


@app.route('/api/keywords', methods=['GET'])
def api_get_keywords():
    return jsonify(load_keywords())


@app.route('/keywords/saveall', methods=['POST'])
def saveall_keywords():
    data = request.get_json()
    keywords = data.get('keywords', [])
    save_keywords(keywords)
    return jsonify({'status': 'ok'})


app.static_folder = 'static'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
