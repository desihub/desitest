import smtplib
import os
import socket
from email.message import Message

def send_email(FromName,To,Subject,Body,Cc=None):

    From = FromName+" <{0}@{1}>".format(os.environ['USER'],socket.getfqdn() + '.nersc.gov')

    msg            = Message()

    msg['From']    = From
    msg['To']      = To
    msg['Subject'] = Subject

    if Cc is not None:
        msg['Cc'] = ",".join(Cc)

    msg.set_payload(Body.encode('utf-8'), 'utf-8')
    
    smtp = smtplib.SMTP('localhost')
    smtp.sendmail(From, [To]+Cc, msg.as_string())
    smtp.quit()

    return
