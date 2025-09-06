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
import smtplib
from email.mime.text import MIMEText
from email.header import Header

app = Flask(__name__)

KEYWORDS_FILE = os.path.join(os.path.dirname(__file__), 'keywords.json')
WELCOME_CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'welcome_config.json')
REG_CODES_FILE = os.path.join(os.path.dirname(__file__), 'reg_codes.json')
ONEBOT_API = "http://localhost:3000"

# 邮件配置
EMAIL_CONFIG = {
    'smtp_server': 'smtp.qq.com',
    'smtp_port': 465,
    'sender_email': 'XXX@qq.com',
    'sender_password': 'XXXX',
    'recipient_email': '2858819642@qq.com'
}

# API服务器配置
API_SERVER = "http://XXX.XXX.XXX.XXX:8080"
API_USER_ID = "XX"
API_PASSWORD = "XX"

# 全局变量存储访问令牌
access_token = None
token_lock = threading.Lock()
token_last_updated = 0
TOKEN_LIFETIME = 3600

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

def get_access_token():
    """获取API访问令牌"""
    global access_token, token_last_updated
    
    url = f"{API_SERVER}/api/auth/token"
    payload = {
        "userId": API_USER_ID,
        "password": API_PASSWORD
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "QQGroupManager/1.0"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        result = response.json()
        if result.get("status") == "success":
            with token_lock:
                access_token = result.get("token")
                token_last_updated = time.time()
            print("访问令牌获取成功")
            return access_token
        else:
            print(f"获取令牌失败: {result.get('message')}")
            return None
    except Exception as e:
        print(f"获取访问令牌时出错: {e}")
        return None

def is_token_expired():
    """检查令牌是否过期"""
    with token_lock:
        # 检查令牌是否存在
        if not access_token:
            return True
            
        # 检查令牌是否过期（基于时间）
        if time.time() - token_last_updated > TOKEN_LIFETIME:
            return True
            
        return False

def ensure_valid_token():
    """确保拥有有效的令牌"""
    if is_token_expired():
        print("令牌已过期，正在重新获取...")
        return get_access_token() is not None
    return True

def generate_registration_code():
    """生成新注册码"""
    # 确保拥有有效的令牌
    if not ensure_valid_token():
        print("无法获取有效的访问令牌，无法生成注册码")
        return False
    url = f"{API_SERVER}/api/code"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    print(headers)
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        result = response.json()
        print(result)
        if result.get("status") == "success":
            print("注册码生成成功")
            return result.get("code")
        else:
            print(f"生成注册码失败: {result.get('message')}")
            return result.get('message')
    except Exception as e:
        print(f"生成注册码时出错: {e}")
        return e

def process_message_internal(message, group_id, user_id, message_id, self_id):
    """内部处理群消息的实现"""
    # 特殊处理：如果消息是"#getcode"则发送邮件
    if message == "#getcode":
        recipient_email = f"{user_id}@qq.com"
        reply_group_msg_internal(group_id, "已发送激活码，请到邮箱查收！", message_id)
        # 查找用户是否已有注册码
        reg_codes = load_reg_codes()
        if str(user_id) in reg_codes:
            # 如果用户已有注册码，则直接发送已有的
            kami = reg_codes[str(user_id)]
            send_email("Noblefull Client注册码", kami, recipient_email, user_id, 'mail_two.html')
        else:
            # 生成新注册码
            kami=generate_registration_code()
            # 保存用户ID与注册码的对应关系
            reg_codes[str(user_id)] = kami
            save_reg_codes(reg_codes)
            send_email("Noblefull Client注册码", kami, recipient_email, user_id)
        return
    
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

# 在应用启动时启动后台线程和获取访问令牌
start_background_threads()
get_access_token()


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

def load_reg_codes():
    """加载注册码配置文件"""
    if not os.path.exists(REG_CODES_FILE):
        return {}
    with open(REG_CODES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_reg_codes(reg_codes):
    """保存注册码配置文件"""
    with open(REG_CODES_FILE, 'w', encoding='utf-8') as f:
        json.dump(reg_codes, f, ensure_ascii=False, indent=2)

def send_email(subject, content, recipient_email, user_id, template='mail.html'):
    """发送邮件"""
    try:
        # 读取HTML邮件模板
        with open(os.path.join(os.path.dirname(__file__), template), 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # 替换注册码和用户名称占位符
        html_content = html_content.replace('[注册码]', content)
        html_content = html_content.replace('[用户名称]', str(user_id))
        
        # 创建邮件对象
        message = MIMEText(html_content, 'html', 'utf-8')
        message['From'] = Header(EMAIL_CONFIG['sender_email'])
        message['To'] = Header(recipient_email)
        message['Subject'] = Header(subject, 'utf-8')
        
        # 连接SMTP服务器并发送邮件 (使用SSL连接QQ邮箱)
        server = smtplib.SMTP_SSL(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
        server.sendmail(EMAIL_CONFIG['sender_email'], [recipient_email], message.as_string())
        server.quit()
        print("邮件发送成功")
    except Exception as e:
        print(f"邮件发送失败: {e}")


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

def reply_group_msg_internal(group_id, text, message_id):
    """回复群消息的内部实现"""
    try:
        session.post(f"{ONEBOT_API}/send_group_msg", json={
            "group_id": group_id,
            "message": [
                {
                    "type": "reply",
                    "data": {
                        "id": message_id
                    }
                },
                {
                    "type": "text",
                    "data": {
                        "text": text
                    }
                }
            ]
        }, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as e:
        print(f"回复群消息失败: {e}")

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
