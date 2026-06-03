"""
desitest.util
=============

Common utility functions.
"""
import smtplib
import os
from email.message import Message


def send_email(FromName, To, Subject, Body, Cc=None):
    """Send mail from `FromName` to `To`.

    Parameters
    ----------
    FromName : :class:`str`
        Name to associate with the sender.
    To : :class:`str`
        Recipient of the message.
    Subject : :class:`str`
        Subject of the message.
    Body : :class:`str`
        Text of the message.
    Cc : :class:`list`, optional
        A list of additional recipients.
    """
    From = f"{FromName} <{os.environ['USER']}@nersc.gov>"

    msg = Message()

    msg['From'] = From
    msg['To'] = To
    msg['Subject'] = Subject

    if Cc is not None:
        if len(Cc) > 0:
            msg['Cc'] = ",".join(Cc)

    msg.set_payload(Body.encode('utf-8'), 'utf-8')

    smtp = smtplib.SMTP('localhost')
    smtp.sendmail(From, [To]+Cc, msg.as_string())
    smtp.quit()

    return
