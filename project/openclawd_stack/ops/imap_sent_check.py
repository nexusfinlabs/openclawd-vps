import imaplib
import os

def check_sent():
    email_addr = "dealflow@nexusfinlabs.com"
    password = os.environ.get("EMAIL_PASSWORD", "")
    server = "imap.ionos.es"
    
    try:
        mail = imaplib.IMAP4_SSL(server)
        mail.login(email_addr, password)
        # IONOS folders often have different names, let's list them
        _, folders = mail.list()
        print("Available folders:")
        for f in folders:
            print(f.decode())
            
        # Try to select the Sent folder (common names: Sent, Sent Messages, INBOX.Sent)
        sent_folder = "Sent"
        # Check if INBOX.Sent exists
        for f in folders:
            if "Sent" in f.decode():
                sent_folder = f.decode().split(' "/" ')[-1].strip('"')
                break
        
        print(f"\nSelecting folder: {sent_folder}")
        mail.select(sent_folder)
        
        # Search for recent messages
        _, data = mail.search(None, "ALL")
        ids = data[0].split()
        print(f"Total messages in Sent: {len(ids)}")
        
        for num in ids[-5:]:
            _, msg_data = mail.fetch(num, "(RFC822.SIZE BODY[HEADER.FIELDS (SUBJECT TO DATE)])")
            print(f"\nMessage {num.decode()}:")
            print(msg_data[0][1].decode())
            
        mail.logout()
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    check_sent()
