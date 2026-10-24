"""Local-only initial admin provisioning: python -m backend.create_admin."""
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv
from . import auth, db, staff

def main():
    root=Path(__file__).resolve().parents[1]
    load_dotenv(root/'.env')
    db.init();auth.init();staff.init()
    with db.connect() as c:
        if c.execute("SELECT 1 FROM staff_accounts WHERE role='admin'").fetchone():
            print('An administrator already exists; no credentials were changed.')
            return
        password=secrets.token_urlsafe(24)
        c.execute('INSERT INTO staff_accounts(id,username,name,role,password_hash,created_at) VALUES(?,?,?,?,?,?)',
            (secrets.token_hex(16),'fmb-admin','Campus administrator','admin',staff.hash_password(password),db.now()))
        target=Path(os.getenv('DATABASE_PATH','data/fixmyblock.db')).resolve().parent/'admin-credentials.txt'
        target.write_text('FixMyBlock initial administrator\nUser ID: fmb-admin\nTemporary password: '+password+'\n\nChoose Maintenance / Admin on the sign-in page.\nYou must change this password at first sign-in.\nKeep this file private and remove it after changing your password.\n',encoding='utf-8')
    print('Initial admin created. Credentials saved locally in '+str(target)+'. They are excluded from Git.')

if __name__=='__main__':main()
