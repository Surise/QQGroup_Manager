import json
import os
from flask import Flask, request, render_template, redirect, url_for, jsonify
import requests
from concurrent.futures import ThreadPoolExecutor
import asyncio
import threading
from functools import partial
from queue import Queue, Empty
import time

app = Flask(__name__)

KEYWORDS_FILE = os.path.join(os.path.dirname(__file__), 'keywords.json')
WELCOME_CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'welcome_config.json')
ONEBOT_API = "http://localhost:3000"

# 创建线程池用于处理API请求
# 调整线程池大小以适应更高并发
executor = ThreadPoolExecutor(max_workers=20)

# 创建会话以复用连接
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=20,
    pool_maxsize=20,
    max_retries=3
)
session.mount('http://', adapter)
session.mount('https://', adapter)

# 添加超时设置
REQUEST_TIMEOUT = 5

# 消息队列用于批量处理
message_queue = Queue()
welcome_queue = Queue()

# 新增异步处理函数
def process_welcome(group_id, message):
    """异步处理欢迎消息"""
    send_group_msg_internal(group_id, message)

def process_message_internal(message, group_id, user_id, message_id, self_id):
    """内部处理群消息的实现"""
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
                    send_group_msg_internal(group_id, cfg.get("reply", ""))
            break

def process_message(message, group_id, user_id, message_id, self_id):
    """异步处理群消息"""
    executor.submit(process_message_internal, message, group_id, user_id, message_id, self_id)

# 启动后台处理线程
def start_background_threads():
    # 启动消息处理线程
    message_thread = threading.Thread(target=message_processor, daemon=True)
    message_thread.start()
    
    # 启动欢迎消息处理线程
    welcome_thread = threading.Thread(target=welcome_processor, daemon=True)
    welcome_thread.start()

def message_processor():
    """后台处理群消息的线程"""
    while True:
        try:
            # 从队列获取消息，超时1秒
            item = message_queue.get(timeout=1)
            if item is None:
                break
            
            message, group_id, user_id, message_id, self_id = item
            process_message_internal(message, group_id, user_id, message_id, self_id)
            message_queue.task_done()
        except Empty:
            continue
        except Exception as e:
            print(f"消息处理出错: {e}")

def welcome_processor():
    """后台处理欢迎消息的线程"""
    while True:
        try:
            # 从队列获取欢迎消息，超时1秒
            item = welcome_queue.get(timeout=1)
            if item is None:
                break
            
            group_id, message = item
            send_group_msg_internal(group_id, message)
            welcome_queue.task_done()
        except Empty:
            continue
        except Exception as e:
            print(f"欢迎消息处理出错: {e}")

# 在应用启动时启动后台线程
start_background_threads()


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
        response = session.post(f"{ONEBOT_API}/get_group_member_info", json={
            "group_id": group_id,
            "user_id": self_id
        }, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'ok' and data.get('data'):
            role = data['data'].get('role')
            return role in ['admin', 'owner']
    except requests.exceptions.RequestException as e:
        print(f"权限检查失败: {e}")
    return False


def recall_message(message_id):
    # 使用线程池异步执行API请求
    executor.submit(session.post, f"{ONEBOT_API}/delete_msg", json={"message_id": message_id}, timeout=REQUEST_TIMEOUT)

def ban_user(group_id, user_id, duration):
    # 使用线程池异步执行API请求
    executor.submit(session.post, f"{ONEBOT_API}/set_group_ban", json={
        "group_id": group_id,
        "user_id": user_id,
        "duration": duration
    }, timeout=REQUEST_TIMEOUT)

def kick_user(group_id, user_id):
    # 使用线程池异步执行API请求
    executor.submit(session.post, f"{ONEBOT_API}/set_group_kick", json={
        "group_id": group_id,
        "user_id": user_id
    }, timeout=REQUEST_TIMEOUT)

def send_group_msg_internal(group_id, text):
    """直接发送群消息的内部实现"""
    try:
        session.post(f"{ONEBOT_API}/send_group_msg", json={
            "group_id": group_id,
            "message": [{"type": "text", "data": {"text": text}}]
        }, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as e:
        print(f"发送群消息失败: {e}")

def send_group_msg(group_id, text):
    """使用线程池异步执行API请求"""
    executor.submit(send_group_msg_internal, group_id, text)


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
                # 将欢迎消息加入队列
                welcome_queue.put((group_id, welcome_config["message"]))
            return jsonify({})
        if data.get("post_type") == "message" and data.get("message_type") == "group":
            message = "".join([seg["data"].get("text", "") for seg in data["message"] if seg["type"] == "text"])
            group_id = data["group_id"]
            user_id = data["user_id"]
            message_id = data["message_id"]
            self_id = data.get("self_id")
            
            # 将消息处理加入队列
            message_queue.put((message, group_id, user_id, message_id, self_id))
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
    app.run(host='0.0.0.0', port=8080)

