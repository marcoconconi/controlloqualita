#!/usr/bin/env python3
import os
import sys
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import smtplib
from email.message import EmailMessage


def send_alert(body):
    sender = "controlloevaso@ponzigroup.eu"
    recipient = 'marco.conconi@ponzi.com'
    
    msg = MIMEMultipart()
    msg["Subject"] = "Schedulazione controllo evaso ERRORE"
    msg["From"]    = "controlloevaso@ponzigroup.eu"
    msg["To"]      = "marco.conconi@ponzi.com"
    SMTP_HOST = 'smtps.aruba.it'
    SMTP_USER = 'controlloevaso@ponzigroup.eu'
    SMTP_PWD = '1Cedc0ff33#'
    msg.attach(MIMEText(body, 'plain'))
    server = smtplib.SMTP_SSL(SMTP_HOST)
    server.login(SMTP_USER, SMTP_PWD)
    text = msg.as_string()
    server.sendmail(sender, recipient, text)
    server.quit()

# － Imposta il path del progetto e carica Django －
PROJECT_DIR = '/data/cqenv/cq_project'
sys.path.insert(0, PROJECT_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cq_project.settings')

import django
django.setup()

from controlloqualita.services.importer import import_csv_file

# — CONFIG — 
IMAP_HOST     = "imaps.aruba.it"
IMAP_USER     = "controlloevaso@ponzigroup.eu"
#IMAP_PASSWORD = os.environ['IMAP_PASSWORD']  # definisci in /etc/environment
IMAP_PASSWORD = "1Cedc0ff33#"
DOWNLOAD_TMP  = "/tmp"
MAILBOX       = "INBOX"

# collegamento IMAP
M = imaplib.IMAP4_SSL(IMAP_HOST)
M.login(IMAP_USER, IMAP_PASSWORD)
M.select(MAILBOX)

# prendi i messaggi non letti
status, data = M.search(None, '(UNSEEN)')
if status != 'OK':
    print("Nessuna risposta IMAP:", status); sys.exit(1)

ids = data[0].split()
if not ids:
    #print("Nessun nuovo messaggio.")
    send_alert("Nessuna mail trovata")
    M.logout()
    sys.exit(0)

# scegli il più recente
latest = ids[-1]
_, msg_data = M.fetch(latest, '(RFC822)')
msg = email.message_from_bytes(msg_data[0][1])

# cerca il primo .csv
attachment_path = None
for part in msg.walk():
    if part.get_content_maintype()=='multipart':
        continue
    disp = part.get("Content-Disposition","")
    if "attachment" in disp:
        fn = part.get_filename()
        if fn and fn.lower().endswith(".csv"):
            dh = decode_header(fn)[0]
            fn = dh[0].decode(dh[1] or 'utf-8') if isinstance(dh[0],bytes) else dh[0]
            attachment_path = os.path.join(DOWNLOAD_TMP, fn)
            with open(attachment_path,'wb') as f:
                f.write(part.get_payload(decode=True))
            #print("Scaricato:", attachment_path)
            break

if not attachment_path:
    #print("Nessun allegato CSV trovato.")
    send_alert("Nessun allegato CSV trovato")
    M.logout()
    sys.exit(0)

# segna come letto
M.store(latest, '+FLAGS', '\\Seen')
M.logout()

# importa direttamente nel DB
#print("Importazione in corso…")
import_csv_file(attachment_path)
#print("Import completato.")
