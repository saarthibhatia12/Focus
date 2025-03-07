import os
import imaplib
import email
import webview
from email.header import decode_header
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, render_template, request, jsonify
from getpass import getuser
from datetime import datetime
from waitress import serve
from dotenv import load_dotenv
from markdown2 import markdown
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama
import fitz
import requests
import time
import json
import html2text
load_dotenv('abc.env')
index = None
query_engine = None

app = Flask(__name__)

# Function to send an email
def send_email(to_email, subject, body):
    from_email = os.getenv('email')
    password = os.getenv('google')

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(from_email, password)
    text = msg.as_string()
    server.sendmail(from_email, to_email, text)
    server.quit()

# Route for handling the email sending
@app.route('/email', methods=['GET', 'POST'])
def email_route():
    if request.method == 'POST':
        to_email = request.form['to_email']
        subject = request.form['subject']
        body = request.form['body']
        send_email(to_email, subject, body)
        mail = login_to_email()
        emails = get_latest_emails(mail)
        return render_template('email.html', emails=emails, success=True)
    else:
        mail = login_to_email()
        emails = get_latest_emails(mail)
        return render_template('email.html', emails=emails)


# Function to login to email
def login_to_email():
    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    mail.login(os.getenv('email'), os.getenv('google'))
    return mail


# Function to get the latest emails
def get_latest_emails(mail, count=10):
    # Initialize HTML to text converter
    h = html2text.HTML2Text()
    h.ignore_links = True  # Don't show link URLs
    h.ignore_images = True  # Don't show image placeholders
    h.ignore_tables = True  # Convert tables to plain text
    h.body_width = 0       # Don't wrap text at a specific width
    
    mail.select('INBOX')
    status, messages = mail.search(None, 'ALL')
    messages = messages[0].split()
    latest_email_ids = messages[-count:] if len(messages) >= count else messages

    emails = []
    for email_id in latest_email_ids:
        status, msg = mail.fetch(email_id, '(RFC822)')
        raw_email = msg[0][1]
        email_message = email.message_from_bytes(raw_email)
        
        # Handle subject
        subject, encoding = decode_header(email_message['Subject'])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding or 'utf-8')
            
        # Handle from field
        from_email, encoding = decode_header(email_message['From'])[0]
        if isinstance(from_email, bytes):
            from_email = from_email.decode(encoding or 'utf-8')
        
        # Handle body
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                        break
                    except:
                        continue
                elif part.get_content_type() == "text/html" and not body:
                    try:
                        html_content = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                        body = h.handle(html_content)
                    except:
                        continue
        else:
            try:
                if email_message.get_content_type() == "text/plain":
                    body = email_message.get_payload(decode=True).decode(email_message.get_content_charset() or 'utf-8')
                elif email_message.get_content_type() == "text/html":
                    html_content = email_message.get_payload(decode=True).decode(email_message.get_content_charset() or 'utf-8')
                    body = h.handle(html_content)
            except Exception as e:
                print(f"Error processing email body: {e}")
                body = "Error reading email content"
        
        # Clean up the body text
        body = body.strip()
        # Remove excessive newlines
        body = '\n'.join(line for line in body.splitlines() if line.strip())
        
        emails.append({'from': from_email, 'subject': subject, 'body': body})

    return emails

# Extract text from PDFs in the "data" directory
def extract_text_from_pdfs(directory):
    for filename in os.listdir(directory):
        if filename.endswith('.pdf'):
            pdf_path = os.path.join(directory, filename)
            txt_path = os.path.join(directory, filename.replace('.pdf', '.txt'))
            
            with fitz.open(pdf_path) as pdf_document:
                text = ""
                for page_num in range(len(pdf_document)):
                    page = pdf_document.load_page(page_num)
                    text += page.get_text()
            
            # Open the output text file with UTF-8 encoding
            with open(txt_path, 'w', encoding='utf-8') as txt_file:
                txt_file.write(text)


TASKS_FILE = 'tasks.json'

def load_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_tasks(tasks):
    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f)

@app.route('/')
def home():
    username = getuser()
    greeting = get_greeting()
    quote = get_quote()
    tasks = load_tasks()
    return render_template('index.html', username=username, greeting=greeting, quote=quote, tasks=tasks)

@app.route('/add_task', methods=['POST'])
def add_task():
    task = request.form['task']
    tasks = load_tasks()
    tasks.append({'text': task, 'completed': False})
    save_tasks(tasks)
    return jsonify(success=True)

@app.route('/toggle_task', methods=['POST'])
def toggle_task():
    index = int(request.form['index'])
    tasks = load_tasks()
    tasks[index]['completed'] = not tasks[index]['completed']
    
    if tasks[index]['completed']:
        del tasks[index]
    
    save_tasks(tasks)
    return jsonify(success=True)
    
def initialize_chat():
    global index, query_engine
    if index is None:
        documents = SimpleDirectoryReader("data").load_data()
        Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-base-en-v1.5")
        Settings.llm = Ollama(model="llama3", request_timeout=360.0)
        index = VectorStoreIndex.from_documents(documents)
        query_engine = index.as_query_engine()

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    global query_engine
    
    if request.method == 'GET':
        return render_template('chat.html', messages=[], username=getuser())

    elif request.method == 'POST':
        try:
            if query_engine is None:
                initialize_chat()
                
            user_message = request.json.get('text_input', '').strip() if request.is_json else request.form.get('text_input', '').strip()
            
            if not user_message:
                return jsonify({'error': 'No message provided.'}), 400

            response = query_engine.query(
                f"Hello llama, the given documents are the context. "
                f"Here is the user question: {user_message}. "
                f"Retrieve the required information from the context knowledge base and explain in neat markdown."
            )

            return jsonify({'content': str(response)})
            
        except Exception as e:
            print(f"Error in chat route: {e}")
            return jsonify({'error': 'Internal server error.'}), 500



def get_greeting():
    now = datetime.now()
    if now.hour < 12:
        return "Good morning"
    elif 12 <= now.hour < 18:
        return "Good afternoon"
    else:
        return "Good evening"

def get_quote():
    response = requests.get('https://zenquotes.io/api/random')
    if response.status_code == 200:
        quote_data = response.json()[0]
        return f"\"{quote_data['q']}\" - {quote_data['a']}"
    else:
        return "Could not retrieve a quote at this time."



if __name__ == '__main__':
    initialize_chat()  # Initialize at startup
    webview.create_window("focus.", app, width=1000, height=800)
    webview.start()
