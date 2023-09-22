from sqlalchemy import (create_engine,text)

def insertEmail(message_id, header, subject, body, fromAddr, to, cc ,received_at, created_by, in_reply_to, ticket_id, critical_type, status, plain_text, email_type):
    engine = create_engine("postgresql://postgres:postgrespassword@18.139.38.227:5432/postgres")
    conn = engine.connect()
    sql_text = text('''
        INSERT INTO public.emails
        (message_id, "header", subject, body, "from", "to", cc, "received_at", created_at, created_by, updated_at, in_reply_to, ticket_id, critical_type, status, plain_text, type)
        VALUES(:message_id, :header, :subject, :body, :fromAddr, :to, :cc, :received_at, now(), :created_by, now(), :in_reply_to, :ticket_id, :critical_type, :status, :plain_text, :email_type);
    ''')
    params = {
        "message_id": message_id,
        "header": header,
        "subject": subject,
        "body": body,
        "fromAddr": fromAddr,
        "to": to,
        "cc": cc,
        "received_at": received_at,
        "created_by": created_by,
        "in_reply_to": in_reply_to,
        "ticket_id": ticket_id,
        "critical_type": critical_type,
        "status": status,
        "plain_text": plain_text,
        "email_type": email_type
    }
    result = conn.execute(sql_text, params)
    conn.commit()
    conn.close()
    return result

def insertEmailAttachments(message_id, file_name, url, file_size):
    engine = create_engine("postgresql://postgres:postgrespassword@18.139.38.227:5432/postgres")
    conn = engine.connect()
    sql_text = text("""
        INSERT INTO public.email_attachments
        (message_id, file_name, url, file_size)
        Values(:message_id, :file_name, :url, :file_size)
    """)
    params = {
        "message_id": message_id,
        "file_name": file_name,
        "url": url,
        "file_size": file_size
    }
    result = conn.execute(sql_text, params)
    conn.commit()
    conn.close()
    return result

def selectCriticalDomain(platform, email):
    engine = create_engine("postgresql://postgres:postgrespassword@18.139.38.227:5432/postgres")
    conn = engine.connect()
    sql_text = text('''
        SELECT *
        FROM public.email_noc_critical
        WHERE email = :email 
        AND platform = :platform
        AND status = 'active'
    ''')
    params = {
        "email": email,
        "platform": platform
    }
    result = conn.execute(sql_text, params)
    conn.commit()
    conn.close()
    return result
