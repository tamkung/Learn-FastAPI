import imaplib
import email
import email.utils
import email.generator
import mailparser
import smtplib
import json
import time 
import pytz
import os
import base64
import quopri
import re

from datetime import datetime, timedelta
from itertools import chain
from sentry_sdk import capture_exception

from app.mail.model import insertEmail, insertEmailAttachments, selectMailCritical
from app.general_utility import convertStrToDate
from app.sentry_config import sentryLog
from app.s3.controller import uploadFileToS3, uploadContentImageToS3

from os.path import basename
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email.mime.message import MIMEMessage
from email.header import decode_header, make_header
from io import StringIO
from dotenv import load_dotenv

load_dotenv()

IMAP_HOST = os.getenv('IMAP_HOST')
IMAP_PORT = os.getenv('IMAP_PORT')
MAIL_USERNAME = os.getenv('MAIL_USERNAME')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT= os.getenv('SMTP_PORT')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL')
CRITERIA = {
    'FROM':    '',
    # 'SUBJECT': 'SPECIAL SUBJECT LINE',
    # 'BODY':    'SECRET SIGNATURE'
}


class Attachment:
    def __init__(self, part, filename=None, type=None, payload=None, charset=None, content_id=None, description=None, disposition=None, sanitized_filename=None, is_body=None):
        self.part=part          # original python part
        self.filename=filename  # filename in unicode (if any) 
        self.type=type          # the mime-type
        self.payload=payload    # the MIME decoded content 
        self.charset=charset    # the charset (if any) 
        self.description=description    # if any 
        self.disposition=disposition    # 'inline', 'attachment' or None
        self.sanitized_filename=sanitized_filename # cleanup your filename here (TODO)  
        self.is_body=is_body        # usually in (None, 'text/plain' or 'text/html')
        self.content_id=content_id  # if any
        if self.content_id:
            # strip '<>' to ease searche and replace in "root" content (TODO) 
            if self.content_id.startswith('<') and self.content_id.endswith('>'):
                self.content_id=self.content_id[1:-1]

def getmailheader(header_text, default="utf-8"):
    """Decode header_text if needed"""
    try:
        headers = decode_header(header_text)
    except email.errors.HeaderParseError:
       return header_text.encode('utf-8', 'replace').decode('utf-8')
    else:
        for i, (text, charset) in enumerate(headers):
            try:
                headers[i] = str(text, charset)
            except:
                # if the charset is unknown, force default 
                headers[i] = text
        return headers[0]

def encoded_words_to_text(encoded_words):
    encoded_word_regex = r'=\?{1}(.+)\?{1}([B|Q])\?{1}(.+)\?{1}='
    charset, encoding, encoded_text = re.match(encoded_word_regex, encoded_words).groups()
    if encoding == 'B':
        byte_string = base64.b64decode(encoded_text)
    elif encoding == 'Q':
        byte_string = quopri.decodestring(encoded_text)
    if charset == 'windows-874':
        charset = 'cp874'
    return byte_string.decode(charset)

def getmailaddresses(msg, name):
    """retrieve addresses from header, 'name' supposed to be from, to,  ..."""
    addrs=email.utils.getaddresses(msg.get_all(name, []))
    for i, (name, addr) in enumerate(addrs):
        if not name and addr:
            # only one string! Is it the address or is it the name ?
            # use the same for both and see later
            name=addr
            
        try:
            # address must be ascii only
            addr=addr.encode('ascii')
        except UnicodeError:
            addr=''
        else:
            # address must match address regex
            if not addr.match(addr):
                addr=''
        addrs[i]=(getmailheader(name), addr)
    return addrs

def get_filename(part):
    """Many mail user agents send attachments with the filename in 
    the 'name' parameter of the 'content-type' header instead 
    of in the 'filename' parameter of the 'content-disposition' header.
    """
    filename=part.get_param('filename', None, 'content-disposition')
    if not filename:
        filename=part.get_param('name', None) # default is 'content-type'
        
    if filename:
        # RFC 2231 must be used to encode parameters inside MIME header
        filename=email.utils.collapse_rfc2231_value(filename).strip()

    if filename and isinstance(filename, str):
        # But a lot of MUA erroneously use RFC 2047 instead of RFC 2231
        # in fact anybody miss use RFC2047 here !!!
        filename=getmailheader(filename)
        
        
    return filename

def _search_message_bodies(bodies, part):
    """recursive search of the multiple version of the 'message' inside 
    the the message structure of the email, used by search_message_bodies()"""
    
    type=part.get_content_type()
    if type.startswith('multipart/'):
        # explore only True 'multipart/*' 
        # because 'messages/rfc822' are also python 'multipart' 
        if type=='multipart/related':
            # the first part or the one pointed by start 
            start=part.get_param('start', None)
            related_type=part.get_param('type', None)
            for i, subpart in enumerate(part.get_payload()):
                if (not start and i==0) or (start and start==subpart.get('Content-Id')):
                    _search_message_bodies(bodies, subpart)
                    return
        elif type=='multipart/alternative':
            # all parts are candidates and latest is best
            for subpart in part.get_payload():
                _search_message_bodies(bodies, subpart)
        elif type in ('multipart/report',  'multipart/signed'):
            # only the first part is candidate
            try:
                subpart=part.get_payload()[0]
            except IndexError:
                return
            else:
                _search_message_bodies(bodies, subpart)
                return

        elif type=='multipart/signed':
            # cannot handle this
            return
            
        else: 
            # unknown types must be handled as 'multipart/mixed'
            # This is the peace of code could probably be improved, I use a heuristic : 
            # - if not already found, use first valid non 'attachment' parts found
            for subpart in part.get_payload():
                tmp_bodies=dict()
                _search_message_bodies(tmp_bodies, subpart)
                for k, v in tmp_bodies.items():
                    if not subpart.get_param('attachment', None, 'content-disposition')=='':
                        # if not an attachment, initiate value if not already found
                        bodies.setdefault(k, v)
            return
    else:
        bodies[part.get_content_type().lower()]=part
        return
    
    return

def search_message_bodies(mail):
    """search message content into a mail"""
    bodies=dict()
    _search_message_bodies(bodies, mail)
    return bodies

def get_mail_contents(msg):
    """split an email in a list of attachments"""

    attachments=[]

    # retrieve messages of the email
    bodies=search_message_bodies(msg)
    # reverse bodies dict
    parts=dict((v,k) for k, v in bodies.items())

    # organize the stack to handle deep first search
    stack=[ msg, ]
    while stack:
        part=stack.pop(0)
        type=part.get_content_type()
        if type.startswith('message/'): 
            # ('message/delivery-status', 'message/rfc822', 'message/disposition-notification'):
            # I don't want to explore the tree deeper her and just save source using msg.as_string()
            # but I don't use msg.as_string() because I want to use mangle_from_=False 
            fp = StringIO()
            g = email.generator.Generator(fp, mangle_from_=False)
            g.flatten(part, unixfrom=False)
            payload=fp.getvalue()
            filename='mail.eml'
            attachments.append(Attachment(part, filename=filename, type=type, payload=payload, charset=part.get_param('charset'), description=part.get('Content-Description')))
        elif part.is_multipart():
            # insert new parts at the beginning of the stack (deep first search)
            stack[:0]=part.get_payload()
        else:
            payload=part.get_payload(decode=True)
            charset=part.get_param('charset')
            filename=get_filename(part)
                
            disposition=None
            if part.get_param('inline', None, 'content-disposition')=='':
                disposition='inline'
            elif part.get_param('attachment', None, 'content-disposition')=='':
                disposition='attachment'
        
            attachments.append(Attachment(part, filename=filename, type=type, payload=payload, charset=charset, content_id=part.get('Content-Id'), description=part.get('Content-Description'), disposition=disposition, is_body=parts.get(part)))

    return attachments

def decode_text(payload, charset, default_charset):
    if charset:
        if charset == 'windows-874' or charset == 'tis-620':
            try:
                return payload.decode('cp874'), charset
            except:
                pass
        try:
            return payload.decode(charset), charset
        except:
            pass

    if default_charset and default_charset!='auto':
        try: 
            return payload.decode(default_charset), default_charset
        except:
            pass
        
    for chset in [ 'ascii', 'utf-8', 'utf-16', 'windows-1252', 'cp850' ]:
        try: 
            return payload.decode(chset), chset
        except:
            pass

    return payload, None


def search_string(uid_max, criteria):
    c = list(map(lambda t: (t[0], '"'+str(t[1])+'"'), criteria.items())) + [('UID', '%d:*' % (uid_max+1))]
    return '(%s)' % ' '.join(chain(*c))


def createDirectory(dir_fd):
    try:
        # Create target Directory
        os.mkdir(dir_fd)
    except FileExistsError:
        pass


def connectImap(folder='"INBOX"'):
    client = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    client.login(MAIL_USERNAME, MAIL_PASSWORD)

    client.select(folder)
    
    print("connect imap success")
    return client


def addTagToEmail(message_id, tag_name, folder='"INBOX"'):
    # Connect IMAP
    if "<" in message_id:
        tmp_message_id = message_id.split("<")
        message_id = "<"+tmp_message_id[1]
    client = connectImap(folder=folder)

    #the search command
    result, data = client.uid('search', '(HEADER Message-ID "%s")' % message_id, None)
    uid = data[0]
    uid = uid.decode("utf-8")
    if " " in uid:
        tmp_uid = uid.split(" ")
        for uid in tmp_uid:
            uid = bytes(uid, "utf-8")
            client.uid("STORE", uid, '+FLAGS', tag_name)
    elif uid=="":
        pass
    else:
        uid = bytes(uid, "utf-8")
        client.uid("STORE", uid, '+FLAGS', tag_name)


def removeTagToEmail(message_id, tag_name, folder='"INBOX"'):
    # Connect IMAP
    if "<" in message_id:
        tmp_message_id = message_id.split("<")
        message_id = "<"+tmp_message_id[1]
    client = connectImap(folder=folder)

    #the search command
    result, data = client.uid('search', '(HEADER Message-ID "%s")' % message_id, None)
    uid = data[0]
    uid = uid.decode("utf-8")
    if " " in uid:
        tmp_uid = uid.split(" ")
        for uid in tmp_uid:
            uid = bytes(uid, "utf-8")
            client.uid("STORE", uid, '-FLAGS', tag_name)
    elif uid=="":
        pass
    else:
        uid = bytes(uid, "utf-8")
        client.uid("STORE", uid, '-FLAGS', tag_name)

def writeFileFromMail(mail):
    createDirectory("tmp")
    name_files = []
    i = 1

    for part in mail.walk():
        if part.get_content_maintype() == 'multipart':
            # print part.as_string()
            continue

        if part.get('Content-Disposition') is None:
            # print part.as_string()
            continue

        name_file = part.get_filename()
        #check extension file
        content_type = part.get_content_type()
        extension_file_check = name_file.split(".")[-1]
        
        if content_type == "image/bmp" and extension_file_check != "bmp":
            name_file = name_file + ".bmp"
        elif content_type == "image/gif" and extension_file_check != "gif":
            name_file = name_file + ".gif"
        elif content_type == "image/vnd.microsoft.icon" and extension_file_check != "ico":
            name_file = name_file + ".ico"
        elif content_type == "image/jpeg" and extension_file_check != "jpg":
            name_file = name_file + ".jpg"
        elif content_type == "image/png" and extension_file_check != "png":
            name_file = name_file + ".png"
        elif content_type == "image/svg+xml" and extension_file_check != "svg":
            name_file = name_file + ".svg"
        elif content_type == "image/tiff" and extension_file_check != "tif":
            name_file = name_file + ".tif"
        elif content_type == "image/webp" and extension_file_check != "webp":
            name_file = name_file + ".webp"
            
        if bool(name_file):
            if name_file is None:
                name_file = ""
            if "\r\n\t" in name_file:
                tmp = name_file.split("\r\n\t")
                count_loop = 0
                name_file = ""
                while count_loop<len(tmp):
                    tmp_name_file = ""
                    try:
                        tmp_name_file = str(tmp[count_loop], 'utf-8')
                    except:
                        tmp_name_file = tmp[count_loop]
                        pass
                    
                    try:
                        tmp_name_file = encoded_words_to_text(encoded_words=tmp_name_file)
                    except Exception:
                        pass

                    try:
                        tmp_name_file = tmp_name_file.decode("utf-8")
                    except Exception:
                        pass

                    name_file = name_file + tmp_name_file
                    count_loop = count_loop+1

            try:
                name_file = encoded_words_to_text(encoded_words=name_file)
            except Exception:
                pass
            name_file = str(i)+"-"+name_file
            content_type = part.get_content_type()
            try:
                size_file = len(part.get_payload(decode=True))/1024
            except Exception:
                size_file = 0
                continue
            if size_file>1024:
                size_file = size_file/1024
                unit_file = "MB"
            else:
                unit_file = "KB"

            fp = open("tmp/"+name_file, 'wb')
            fp.write(part.get_payload(decode=True))
            fp.close()
            name_files.append({"name_file": name_file, "content_type": content_type, "size_file": str(round(size_file, 2))+" "+unit_file})
            i=i+1

    return name_files

def uploadContentImage(message_id, content_id, payload, content_type):
    createDirectory("tmp")
    if content_id is None:
        content_id = "None"

    size_file = len(payload)/1024
    if size_file>1024:
        size_file = size_file/1024
        unit_file = "MB"
    else:
        unit_file = "KB"

    if content_type == "image/bmp":
        name_file = content_id+".bmp"
        extension_name = ".bmp"
    elif content_type == "image/gif":
        name_file = content_id+".gif"
        extension_name = ".gif"
    elif content_type == "image/vnd.microsoft.icon":
        name_file = content_id+".ico"
        extension_name = ".ico"
    elif content_type == "image/jpeg":
        name_file = content_id+".jpg"
        extension_name = ".jpg"
    elif content_type == "image/png":
        name_file = content_id+".png"
        extension_name = ".png"
    elif content_type == "image/svg+xml":
        name_file = content_id+".svg"
        extension_name = ".svg"
    elif content_type == "image/tiff":
        name_file = content_id+".tif"
        extension_name = ".tif"
    elif content_type == "image/webp":
        name_file = content_id+".webp"
        extension_name = ".bmp"
    else:
        name_file = content_id
        extension_name = ".jpg"

    fp = open("tmp/"+name_file, 'wb')
    fp.write(payload)
    fp.close()
    name_files = {"name_file": name_file, "content_type": content_type, "size_file": str(round(size_file, 2))+" "+unit_file}
    #result = ""
    result = uploadContentImageToS3(filename=name_files, message_id=message_id)

    return {
        "path": result,
        "name": content_id,
        "extension": extension_name
    }

def receive_mail_all_folder():
    print("begin")
    folder = ['"INBOX"']
    for item in folder:
        print(item)
        receiveMail(folder=item)
        
    return {
        "message": "success"
    }

def receiveMail(folder):
    log_obj = sentryLog()
    print("connecting imap")
    
    # Connect IMAP
    client = connectImap(folder=folder)
    CURRENT_NOW = datetime.now(pytz.utc)
    #CURRENT_NOW = datetime.now(pytz.utc) - timedelta(days=5)
    CRITERIA = {
        'FROM': '',
        'SINCE': CURRENT_NOW.date().strftime("%d-%b-%Y")
    }

    # Fetch UID Email
    print("fetching uid")
    result, data = client.uid('search', None, '(UNSEEN)', '(SINCE {date})'.format(date=CRITERIA['SINCE']))
    #result, data = client.uid('search', 'UNSEEN', search_string(0, CRITERIA))
    print("fetch uid success")

    if not data or len(data[0].split()) == 0:
        print("no email fetched")
        client.logout()
        return

    print(len(data[0].split()))
    try:
        uids = [int(s) for s in data[0].split()]
    except ValueError:
        # Handle the case where the data contains unexpected values
        print("Error: Unexpected data from the IMAP server")
        client.logout()
        return
    print("uids: ", uids)
    
    # Loop through the list of email UIDs
    for uid in uids:
        print("fetching mail")
        result, data = client.uid('fetch', str(uid), '(RFC822)')  # Fetch by UID per email
        print("fetch mail success")
        
        # Fetch Get Message ID 's email
        result_message_id, data_message_id = client.uid('fetch', str(uid), '(BODY[HEADER.FIELDS (MESSAGE-ID)])')
        print("fetch header success")
        
        msg_str = email.message_from_bytes(data_message_id[0][1])
        
        try:
            mail = mailparser.parse_from_bytes(data[0][1])
        except Exception:
            try:
                response = data[1]
                mail = mailparser.parse_from_bytes(response[1])
            except Exception:
                try:
                    for item in data:
                        try:
                            mail = mailparser.parse_from_bytes(item)
                            break
                        except Exception:
                            continue
                except Exception:
                    print(data)
                    error_id = capture_exception(Exception)
                    log_obj.event_id = error_id
                    log_obj._error()
                    print(Exception)
                    client.uid("STORE", str(uid), '-FLAGS', '(\Seen)')
                    continue

        mail_header = json.loads(mail.headers_json)  # Get the header
        if folder == 'Sent':  # Remove the double quotes around "Sent"
            date = datetime.now(pytz.utc)
        else:
            date = mail_header.get("Date") or mail_header.get("date")
            try:
                date = convertStrToDate(date)
            except Exception:
                date = datetime.now(pytz.utc)

        hours_offset = int(int(date.utcoffset().total_seconds()) / 3600)

        # Check receive time mail before open function must pass
        if date < CURRENT_NOW:
            # client.uid("STORE", str(uid), '-FLAGS', '(\Seen)')
            # continue
            pass
        try:
            message_id = msg_str.get('Message-ID').replace(" ", "").replace('\n','').replace('\r','')
        except Exception:
            print(Exception)
            pass
        
        try:
            msg = email.message_from_bytes(data[0][1])
        except Exception:
            try:
                response=data[1]
                msg = email.message_from_bytes(response[1])
            except Exception:
                try:
                    for item in data:
                        try:
                            msg = email.message_from_bytes(item)
                            break
                        except Exception:
                            continue
                except Exception:
                    print(data)
                    error_id = capture_exception(Exception)
                    log_obj.event_id = error_id
                    log_obj._error()
                    print(Exception)
                    client.uid("STORE", str(uid), '-FLAGS', '(\Seen)')
                    continue
                    
        subject = '<No Subject>'
        if msg['subject']:
            tmp_text = decode_header(msg['subject'])
            count_loop = 0
            subject = ""
            while count_loop<len(tmp_text):
                text, encoding = tmp_text[count_loop]
                try:
                    print(encoding)
                except:
                    encoding = None
                if encoding == None:
                    tmp_subject = text
                elif encoding != 'utf-8':
                    tmp_subject = str(text, 'cp874')
                else:
                    tmp_subject = str(text, 'utf-8')
                
                try:
                    tmp_subject = encoded_words_to_text(encoded_words=tmp_subject)
                except Exception:
                    print(Exception)
                    pass

                try:
                    tmp_subject = tmp_subject.decode("utf-8")
                except Exception:
                    print(Exception)
                    pass
                subject = subject + tmp_subject
                count_loop = count_loop+1

        print(subject)
        messages = get_mail_contents(msg)
        plain_text = None
        html_text = None
        image_attachs = []
        for message in messages:
            if message.is_body=='text/plain':
                plain_text, used_charset=decode_text(message.payload, message.charset, 'auto')
            elif message.is_body=='text/html':
                html_text, used_charset=decode_text(message.payload, message.charset, 'auto')
            elif message.part.get_content_type().startswith('image/'):
                image_attach_upload_s3 = uploadContentImage(message_id, message.content_id, message.payload, message.part.get_content_type())
                image_attachs.append(image_attach_upload_s3)

        if html_text:
            for value in image_attachs:
                print(value)
                html_text = html_text.replace('cid:' + value['name'], S3_ENDPOINT_URL + S3_BUCKET_NAME + '/' + value['path'])


        # write attachments file
        mail_file = writeFileFromMail(msg)

        # upload file to s3
        for item in mail_file:
            filename_output = uploadFileToS3(filename=item, message_id=str(message_id))
            url = S3_ENDPOINT_URL + S3_BUCKET_NAME + "/" + filename_output
            insertEmailAttachments(message_id=str(message_id), file_name=item["name_file"], url=url, file_size=item["size_file"])

        #bind parameter
        fromAddr = mail_header.get("From", None)
        if fromAddr is None:
            fromAddr = mail_header.get("from", None)

        toAddr = mail_header.get("To", None)
        if toAddr is None:
            toAddr = mail_header.get("to", None)
            if toAddr is None:
                toAddr = ""

        if toAddr is not None:
            toAddr = toAddr.replace("\r","")
            toAddr = toAddr.replace("\n","")
            toAddr = toAddr.replace("\t","")

        ccAddr = mail_header.get("Cc", None)
        if ccAddr is None:
            ccAddr = mail_header.get("CC", None)

        tmp_cc = ""
        if ccAddr is not None:
            ccAddr = ccAddr.replace("\r","")
            ccAddr = ccAddr.replace("\n","")
            ccAddr = ccAddr.replace("\t","")
            tmp_cc = ccAddr.split(",")
            tmp_cc = list(set(tmp_cc))

        inReplyTo = mail_header.get("In-Reply-To", None)
        references = mail_header.get("References", None)

        ccAddr = ""
        for item in tmp_cc:
            try:
                ccAddr = ccAddr +","+ encoded_words_to_text(encoded_words=item)
            except Exception:
                ccAddr = ccAddr+","+item
                pass
        ccAddr = ccAddr.replace(",","",1)
        tmp_to = toAddr.split(",")
        toAddr = ""

        for item in tmp_to:
            try:
                toAddr = toAddr +","+ encoded_words_to_text(encoded_words=item)
            except Exception:
                toAddr = toAddr+","+item
                pass
        toAddr = toAddr.replace(",","",1)

        if not html_text:
            body = '<div>' + plain_text + '</div>'
        else:
            body = html_text

        if "<" in fromAddr:
            tmp_from = fromAddr.split("<")
            mail_from = tmp_from[1].replace(">","")
        else:
            mail_from = fromAddr
        print(mail_from)
        #Check Domain in Email with Critical Domain
        # critical_domain = ''
        mail_critical = selectMailCritical(email=mail_from)
        print(len(mail_critical))
        if len(mail_critical) > 0:
            critical_type = True
        else:
            critical_type = False
        
        #Parse the date in email
        try:
            date_timestamp = date.replace(tzinfo=pytz.utc).astimezone(tz=None).timestamp()
            date_timestamp = datetime.fromtimestamp(date_timestamp, pytz.timezone("UTC")) - timedelta(hours=hours_offset)
        except Exception:
            date_timestamp = datetime.now(pytz.utc)

        ticket_id = None
        try:
            #Insert Email in to Database
            if folder =='"Sent"':
                insertEmail(
                    str(message_id), 
                    str(mail_header), 
                    subject, str(body), 
                    str(fromAddr), str(toAddr), 
                    str(ccAddr) ,date_timestamp, 
                    'system',
                    inReplyTo, 
                    ticket_id,
                    critical_type,
                    "sent",
                    plain_text,
                    'email'
                )
            else:
                insertEmail(
                    str(message_id), 
                    str(mail_header), 
                    subject, str(body), 
                    str(fromAddr), str(toAddr), 
                    str(ccAddr) ,date_timestamp, 
                    'system',
                    inReplyTo, 
                    ticket_id,
                    critical_type,
                    "active",
                    plain_text,
                    'email'
                )
        except Exception as error:
            print(error)
            #updateTypeEmailByMessageId(type="email", message_id=message_id, updated_by="system")
            pass

        try:
            addTagToEmail(message_id=str(message_id), tag_name="EMT")

            if folder !='"Sent"':
                print(str(message_id))
                #result_email = selectEmailByMessageID(message_id=str(message_id))
                #checkFilter(email=result_email)
        except Exception as error:
            error_id = capture_exception(error)
            log_obj.event_id = error_id
            log_obj._error()
            print(error)
            continue
    client.logout()

from pydantic import BaseModel
from fastapi import FastAPI, File, UploadFile
from typing import List
class EmailPayload(BaseModel):
    body: str
    message_id: str
    fwd: bool

async def replyEmail(payload: EmailPayload):
    original_email = fetchEmailByMessageID(payload.message_id)
    
    if original_email is None:
        return {"error": "Original email not found"}
    
    reply_subject = f"Re: {original_email['subject']}"
    reply_body = f"Original email: {original_email['body']}"
    
    sendMail(
        host=SMTP_HOST, port=SMTP_PORT, username=MAIL_USERNAME, password=MAIL_PASSWORD,
        fromAddr=MAIL_USERNAME, toAddr=payload.toAddr, ccAddr="", Subject=reply_subject,
        body=reply_body, message_id=payload.message_id, fwd=False, bccAddr=""
    )
    
    return {"message": "Reply sent successfully"}

async def forwardEmail(payload: EmailPayload, forward_to: str):
    original_email = fetchEmailByMessageID(payload.message_id)
    
    if original_email is None:
        return {"error": "Original email not found"}
    
    forward_subject = f"Fwd: {original_email['subject']}"
    forward_body = f"Forwarded email: {original_email['body']}"
    
    sendMail(
        host=SMTP_HOST, port=SMTP_PORT, username=MAIL_USERNAME, password=MAIL_PASSWORD,
        fromAddr=MAIL_USERNAME, toAddr=forward_to, ccAddr="", Subject=forward_subject,
        body=forward_body, message_id="", fwd=True, bccAddr=""
    )
    
    return {"message": "Email forwarded successfully"}


def fetchEmailByMessageID(message_id):
    try:
        # Connect to the IMAP server
        imap_server = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        imap_server.login(MAIL_USERNAME, MAIL_PASSWORD)

        # Search for the email with the specified message_id
        imap_server.select("inbox")  # You may need to specify the mailbox

        # Search for the email based on message_id
        search_query = f"HEADER Message-ID {message_id}"
        _, data = imap_server.search(None, search_query)

        # Get the email IDs matching the search
        email_ids = data[0].split()

        if not email_ids:
            print("Email not found")
            return None

        # Fetch the email by ID
        _, msg_data = imap_server.fetch(email_ids[0], "(RFC822)")

        # Parse the email content
        raw_email = msg_data[0][1]
        email_message = email.message_from_bytes(raw_email)

        # You can access email attributes like subject, sender, body, etc.
        subject = decode_header(email_message["Subject"])[0][0]
        sender = email_message["From"]
        body = ""

        if email_message.is_multipart():
            for part in email_message.walk():
                #content_type html
                if part.get_content_type() == "text/html":
                    content = part.get_payload(decode=True)
                    content = content.decode("utf-8")
                    body = content
                    break
        else:
            body = email_message.get_payload(decode=True).decode("utf-8")
        
        #decode subject
        try:
            subject = str(subject, 'utf-8')
        except:
            pass
        
        # Close the IMAP connection
        imap_server.logout()

        return {
            "subject": subject,
            "sender": sender,
            "body": body,
            # Add other email attributes as needed
        }

    except Exception as e:
        print(f"Failed to fetch email: {e}")
        return None

def sendMail(host, port, username, password, fromAddr, toAddr, ccAddr, Subject, body, message_id, fwd, bccAddr):
    print("host: ", host)
    print("port: ", port)
    print("username: ", username)
    print("password: ", password)
    # Create an SMTP connection
    try:
        server = smtplib.SMTP(host, port)
        print("connect smtp success1")
        server.starttls()
        print("connect smtp success2")
        server.login(username, password)
        
        print("connect smtp success3")
    except Exception as e:
        print(f"Failed to connect to SMTP server: {e}")
        return

    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = fromAddr
    msg['To'] = toAddr
    msg['Cc'] = ccAddr
    msg['Subject'] = Subject

    # Add the email body
    #msg.attach(MIMEText(body, 'plain'))
    msg.attach(MIMEText(body, 'html', 'utf-8'))

    # If it's a forward, include a forwarded message ID
    if fwd:
        msg.add_header('In-Reply-To', message_id)
        msg.add_header('References', message_id)

    # Send the email
    try:
        server.sendmail(fromAddr, [toAddr, ccAddr, bccAddr], msg.as_string())
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")
    
    # Close the SMTP connection
    server.quit()


def netflixForwardEmail():
    folder = '"INBOX"'
    print("connecting imap")
    
    # Connect IMAP
    client = connectImap(folder=folder)
    #CURRENT_NOW = datetime.now(pytz.utc)
    CURRENT_NOW = datetime.now(pytz.utc) - timedelta(days=5)
    CRITERIA = {
        'FROM': '',
        'SINCE': CURRENT_NOW.date().strftime("%d-%b-%Y")
    }

    # Fetch UID Email
    print("fetching uid")
    result, data = client.uid('search', None, '(UNSEEN)', '(SINCE {date})'.format(date=CRITERIA['SINCE']))
    #result, data = client.uid('search', 'UNSEEN', search_string(0, CRITERIA))
    print("fetch uid success")

    if not data or len(data[0].split()) == 0:
        print("no email fetched")
        client.logout()
        return

    print(len(data[0].split()))
    try:
        uids = [int(s) for s in data[0].split()]
    except ValueError:
        # Handle the case where the data contains unexpected values
        print("Error: Unexpected data from the IMAP server")
        client.logout()
        return
    print("uids: ", uids)
    
    # Loop through the list of email UIDs
    for uid in uids:
        print("fetching mail")
        result, data = client.uid('fetch', str(uid), '(RFC822)')  # Fetch by UID per email
        print("fetch mail success")
        
        # Fetch Get Message ID 's email
        result_message_id, data_message_id = client.uid('fetch', str(uid), '(BODY[HEADER.FIELDS (MESSAGE-ID)])')
        print("fetch header success")
        
        msg_str = email.message_from_bytes(data_message_id[0][1])
        
        try:
            mail = mailparser.parse_from_bytes(data[0][1])
        except Exception:
            try:
                response = data[1]
                mail = mailparser.parse_from_bytes(response[1])
            except Exception:
                try:
                    for item in data:
                        try:
                            mail = mailparser.parse_from_bytes(item)
                            break
                        except Exception:
                            continue
                except Exception:
                    print(data)
                    print(Exception)
                    client.uid("STORE", str(uid), '-FLAGS', '(\Seen)')
                    continue

        mail_header = json.loads(mail.headers_json)  # Get the header

        date = mail_header.get("Date") or mail_header.get("date")
        try:
            date = convertStrToDate(date)
        except Exception:
            date = datetime.now(pytz.utc)

        # Check receive time mail before open function must pass
        if date < CURRENT_NOW:
            # client.uid("STORE", str(uid), '-FLAGS', '(\Seen)')
            # continue
            pass
        try:
            message_id = msg_str.get('Message-ID').replace(" ", "").replace('\n','').replace('\r','')
        except Exception:
            print(Exception)
            pass
        
        try:
            original_email = fetchEmailByMessageID(str(message_id))
        except Exception:
            print(Exception)
            pass
        if original_email is None:
            return print("Original email not found")
        
        forward_subject = f"Fw: {original_email['subject']}"
        forward_body = f"Forwarded email: {original_email['body']}"
        print(forward_body)
        
        toAddr = None
        if "ขอโดย TamWT" in forward_body:
            return print("Is Owner Email")
        elif "ขอโดย Pin" in forward_body:
            print("Pin")
            toAddr = "pin@gmail.com"
        elif "ขอโดย DOG" in forward_body:
            print("DOG")
            toAddr = "dog@gmail.com"
        elif "ขอโดย Mini" in forward_body:
            print("Mini")
            toAddr = "mini@gmail.com"
        elif "ขอโดย Peat" in forward_body:
            print("Peat")
            toAddr = "peat@gmail.com"
        else:
            return print("No recipient found")
        
        if toAddr is None:
            return print("No recipient found")
        
        sendMail(
            host=SMTP_HOST,
            port=SMTP_PORT,
            username=MAIL_USERNAME,
            password=MAIL_PASSWORD,
            fromAddr=MAIL_USERNAME,
            toAddr=toAddr,
            ccAddr="",
            bccAddr="",
            Subject=forward_subject,
            body=forward_body,
            message_id="",
            fwd=True,
        )

    client.logout()