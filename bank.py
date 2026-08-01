import os
import random
import hashlib
from datetime import datetime

from database import (
    get_connection, init_db, BANK_IFSC_CODE, PROFILE_PHOTO_DIR, UPI_DOMAIN,
    STATUS_ACTIVE, STATUS_FROZEN, STATUS_SUSPENDED,
)

init_db()


def _status_block_reason(row, for_login=False):
    """Return an error message if this account's status should block the
    action, or None if the action is allowed."""
    status = row["status"] if "status" in row.keys() else STATUS_ACTIVE
    if status == STATUS_SUSPENDED:
        return "This account has been suspended by the bank. Please contact support."
    if status == STATUS_FROZEN and not for_login:
        return "This account is frozen. Transactions are disabled until it's unfrozen by the bank."
    return None


def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()


def _now():
    dt = datetime.now()
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")


class Bank:
    
    def create_account_streamlit(self, user_data: dict):
        conn = get_connection()
        cur = conn.cursor()

        mobile_number = user_data.get("mobile_number", "").strip()

        
        if mobile_number:
            cur.execute("SELECT 1 FROM accounts WHERE mobile_number = ?", (mobile_number,))
            if cur.fetchone():
                conn.close()
                return False, "An account already exists with this mobile number."

        
        while True:
            account_number = str(random.randint(10**9, 10**10 - 1))
            cur.execute(
                "SELECT 1 FROM accounts WHERE account_number = ?",
                (account_number,),
            )
            if not cur.fetchone():
                break

        pin_hash = _hash_pin(user_data["pin"])
        date_str, _ = _now()
        upi_id = f"{mobile_number}@{UPI_DOMAIN}" if mobile_number else None

        try:
            cur.execute(
                """INSERT INTO accounts
                   (account_number, name, age, email, address, pin_hash,
                    ifsc_code, balance, wallet_balance, created_at,
                    mobile_number, upi_id, profile_photo_path, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    account_number,
                    user_data["name"],
                    user_data["age"],
                    user_data["email"],
                    user_data["address"],
                    pin_hash,
                    BANK_IFSC_CODE,
                    0.0,
                    0.0,
                    date_str,
                    mobile_number or None,
                    upi_id,
                    None,
                    STATUS_ACTIVE,
                ),
            )
            conn.commit()
        except Exception as e:
            conn.close()
            return False, f"Could not create account: {e}"

        conn.close()
        return True, {
            "account_number": account_number,
            "IFSC_code": BANK_IFSC_CODE,
            "balance": 0.0,
            "upi_id": upi_id,
        }

    def _get_account(self, cur, account_number, pin=None):
        cur.execute(
            "SELECT * FROM accounts WHERE account_number = ?",
            (account_number,),
        )
        row = cur.fetchone()
        if not row:
            return None
        if pin is not None and row["pin_hash"] != _hash_pin(pin):
            return None
        return row

    def login_streamlit(self, account_number, pin):
        conn = get_connection()
        cur = conn.cursor()
        row = self._get_account(cur, account_number, pin)
        conn.close()
        if not row:
            return False, "Invalid account number or PIN"
        block_reason = _status_block_reason(row, for_login=True)
        if block_reason:
            return False, block_reason
        return True, dict(row)

    def show_details_streamlit(self, account_number, pin):
        conn = get_connection()
        cur = conn.cursor()
        row = self._get_account(cur, account_number, pin)
        conn.close()
        return dict(row) if row else None

    
    def check_balance_streamlit(self, account_number, pin):
        conn = get_connection()
        cur = conn.cursor()
        row = self._get_account(cur, account_number, pin)
        conn.close()
        if not row:
            return False, "Invalid account number or PIN"
        return True, row["balance"]

    def _log_transaction(self, cur, account_number, txn_type, amount, balance_after, description):
        date_str, time_str = _now()
        cur.execute(
            """INSERT INTO transactions
               (account_number, type, amount, balance_after, description, date, time)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (account_number, txn_type, amount, balance_after, description, date_str, time_str),
        )

    def deposit_streamlit(self, account_number, pin, amount):
        if amount <= 0:
            return False, "Amount must be greater than zero"

        conn = get_connection()
        cur = conn.cursor()
        row = self._get_account(cur, account_number, pin)
        if not row:
            conn.close()
            return False, "Invalid account number or PIN"
        block_reason = _status_block_reason(row)
        if block_reason:
            conn.close()
            return False, block_reason

        new_balance = row["balance"] + amount
        cur.execute(
            "UPDATE accounts SET balance = ? WHERE account_number = ?",
            (new_balance, account_number),
        )
        self._log_transaction(cur, account_number, "Deposit", amount, new_balance, "Cash deposit")
        conn.commit()
        conn.close()
        return True, f"₹{amount:.2f} deposited successfully. New balance: ₹{new_balance:.2f}"

    def withdraw_streamlit(self, account_number, pin, amount):
        if amount <= 0:
            return False, "Amount must be greater than zero"

        conn = get_connection()
        cur = conn.cursor()
        row = self._get_account(cur, account_number, pin)
        if not row:
            conn.close()
            return False, "Invalid account number or PIN"
        block_reason = _status_block_reason(row)
        if block_reason:
            conn.close()
            return False, block_reason

        if row["balance"] < amount:
            conn.close()
            return False, "Insufficient balance"

        new_balance = row["balance"] - amount
        cur.execute(
            "UPDATE accounts SET balance = ? WHERE account_number = ?",
            (new_balance, account_number),
        )
        self._log_transaction(cur, account_number, "Withdraw", amount, new_balance, "Cash withdrawal")
        conn.commit()
        conn.close()
        return True, f"₹{amount:.2f} withdrawn successfully. New balance: ₹{new_balance:.2f}"

    
    def transfer_streamlit(self, sender_account, sender_pin, receiver_account, amount, receiver_ifsc=None):
        """
        Transfers money bank-balance to bank-balance.
        If receiver_ifsc is provided, it must match ENZ Bank's IFSC code
        (this app models ENZ Bank as a single branch, so any transfer
        target must be an ENZ Bank account).
        """
        if amount <= 0:
            return False, "Amount must be greater than zero"

        if sender_account == receiver_account:
            return False, "Cannot transfer to your own account"

        conn = get_connection()
        cur = conn.cursor()

        sender = self._get_account(cur, sender_account, sender_pin)
        if not sender:
            conn.close()
            return False, "Invalid sender account number or PIN"
        block_reason = _status_block_reason(sender)
        if block_reason:
            conn.close()
            return False, block_reason

        receiver = self._get_account(cur, receiver_account)
        if not receiver:
            conn.close()
            return False, "Receiver account not found"
        if receiver["status"] == STATUS_SUSPENDED:
            conn.close()
            return False, "Receiver account is suspended and cannot accept transfers."
        if receiver["status"] == STATUS_FROZEN:
            conn.close()
            return False, "Receiver account is frozen and cannot accept transfers."

        if receiver_ifsc is not None:
            if receiver_ifsc.strip().upper() != receiver["ifsc_code"]:
                conn.close()
                return False, "IFSC code does not match the receiver's bank. Transfer rejected."

        if sender["balance"] < amount:
            conn.close()
            return False, "Insufficient balance"

        new_sender_balance = sender["balance"] - amount
        new_receiver_balance = receiver["balance"] + amount

        cur.execute(
            "UPDATE accounts SET balance = ? WHERE account_number = ?",
            (new_sender_balance, sender_account),
        )
        cur.execute(
            "UPDATE accounts SET balance = ? WHERE account_number = ?",
            (new_receiver_balance, receiver_account),
        )

        self._log_transaction(
            cur, sender_account, "Transfer Sent", amount, new_sender_balance,
            f"To {receiver_account} (IFSC {receiver['ifsc_code']})"
        )
        self._log_transaction(
            cur, receiver_account, "Transfer Received", amount, new_receiver_balance,
            f"From {sender_account}"
        )

        conn.commit()
        conn.close()
        return True, f"₹{amount:.2f} transferred successfully to {receiver_account}"

    
    def wallet_topup_streamlit(self, account_number, pin, amount):
        """Move money from bank balance into wallet balance."""
        if amount <= 0:
            return False, "Amount must be greater than zero"

        conn = get_connection()
        cur = conn.cursor()
        row = self._get_account(cur, account_number, pin)
        if not row:
            conn.close()
            return False, "Invalid account number or PIN"
        block_reason = _status_block_reason(row)
        if block_reason:
            conn.close()
            return False, block_reason
        if row["balance"] < amount:
            conn.close()
            return False, "Insufficient bank balance"

        new_balance = row["balance"] - amount
        new_wallet = row["wallet_balance"] + amount
        cur.execute(
            "UPDATE accounts SET balance = ?, wallet_balance = ? WHERE account_number = ?",
            (new_balance, new_wallet, account_number),
        )
        self._log_transaction(cur, account_number, "Wallet Top-up", amount, new_balance, "Bank -> Wallet")
        conn.commit()
        conn.close()
        return True, f"₹{amount:.2f} added to wallet. Wallet balance: ₹{new_wallet:.2f}"

    def wallet_withdraw_streamlit(self, account_number, pin, amount):
        """Move money from wallet balance back into bank balance."""
        if amount <= 0:
            return False, "Amount must be greater than zero"

        conn = get_connection()
        cur = conn.cursor()
        row = self._get_account(cur, account_number, pin)
        if not row:
            conn.close()
            return False, "Invalid account number or PIN"
        block_reason = _status_block_reason(row)
        if block_reason:
            conn.close()
            return False, block_reason
        if row["wallet_balance"] < amount:
            conn.close()
            return False, "Insufficient wallet balance"

        new_balance = row["balance"] + amount
        new_wallet = row["wallet_balance"] - amount
        cur.execute(
            "UPDATE accounts SET balance = ?, wallet_balance = ? WHERE account_number = ?",
            (new_balance, new_wallet, account_number),
        )
        self._log_transaction(cur, account_number, "Wallet Withdrawal", amount, new_balance, "Wallet -> Bank")
        conn.commit()
        conn.close()
        return True, f"₹{amount:.2f} moved back to bank balance."

    def wallet_pay_streamlit(self, payer_account, payer_pin, receiver_account, amount):
        """Pay another user directly wallet-to-wallet (used by scan & pay)."""
        if amount <= 0:
            return False, "Amount must be greater than zero"
        if payer_account == receiver_account:
            return False, "Cannot pay yourself"

        conn = get_connection()
        cur = conn.cursor()

        payer = self._get_account(cur, payer_account, payer_pin)
        if not payer:
            conn.close()
            return False, "Invalid account number or PIN"
        block_reason = _status_block_reason(payer)
        if block_reason:
            conn.close()
            return False, block_reason

        receiver = self._get_account(cur, receiver_account)
        if not receiver:
            conn.close()
            return False, "Receiver account not found"
        if receiver["status"] in (STATUS_SUSPENDED, STATUS_FROZEN):
            conn.close()
            return False, "Receiver account cannot accept payments right now."

        if payer["wallet_balance"] < amount:
            conn.close()
            return False, "Insufficient wallet balance"

        new_payer_wallet = payer["wallet_balance"] - amount
        new_receiver_wallet = receiver["wallet_balance"] + amount

        cur.execute(
            "UPDATE accounts SET wallet_balance = ? WHERE account_number = ?",
            (new_payer_wallet, payer_account),
        )
        cur.execute(
            "UPDATE accounts SET wallet_balance = ? WHERE account_number = ?",
            (new_receiver_wallet, receiver_account),
        )

        self._log_transaction(
            cur, payer_account, "Wallet Pay Sent", amount, payer["balance"],
            f"Paid {receiver_account} via wallet"
        )
        self._log_transaction(
            cur, receiver_account, "Wallet Pay Received", amount, receiver["balance"],
            f"Received from {payer_account} via wallet"
        )

        conn.commit()
        conn.close()
        return True, f"₹{amount:.2f} paid to {receiver_account} via wallet"

    def lookup_account_name(self, account_number):
        """Public-safe lookup: returns just the account holder's name (for
        confirming a scan-and-pay recipient), no balance or PIN exposed."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM accounts WHERE account_number = ?", (account_number,))
        row = cur.fetchone()
        conn.close()
        return row["name"] if row else None

    def get_wallet_balance_streamlit(self, account_number, pin):
        conn = get_connection()
        cur = conn.cursor()
        row = self._get_account(cur, account_number, pin)
        conn.close()
        if not row:
            return False, "Invalid account number or PIN"
        return True, row["wallet_balance"]

    
    def update_account_streamlit(self, account_number, pin, name, email, address):
        """Legacy signature, kept for backward compatibility."""
        return self.update_profile_streamlit(account_number, pin, name=name, email=email, address=address)

    def update_profile_streamlit(self, account_number, pin, name=None, email=None,
                                  address=None, mobile_number=None, photo_bytes=None,
                                  photo_ext="png"):
        """
        Update the caller's own profile. This is the ONLY way profile data
        can change — there is no admin equivalent. Any field left blank/None
        keeps its existing value.
        """
        conn = get_connection()
        cur = conn.cursor()
        row = self._get_account(cur, account_number, pin)
        if not row:
            conn.close()
            return False, "Invalid account number or PIN"

        new_name = name.strip() if name and name.strip() else row["name"]
        new_email = email.strip() if email and email.strip() else row["email"]
        new_address = address.strip() if address and address.strip() else row["address"]

        new_mobile = row["mobile_number"]
        new_upi = row["upi_id"]
        if mobile_number and mobile_number.strip() and mobile_number.strip() != row["mobile_number"]:
            mobile_clean = mobile_number.strip()
            cur.execute(
                "SELECT 1 FROM accounts WHERE mobile_number = ? AND account_number != ?",
                (mobile_clean, account_number),
            )
            if cur.fetchone():
                conn.close()
                return False, "That mobile number is already linked to another account."
            new_mobile = mobile_clean
            new_upi = f"{mobile_clean}@{UPI_DOMAIN}"

        new_photo_path = row["profile_photo_path"]
        if photo_bytes:
            photo_path = os.path.join(PROFILE_PHOTO_DIR, f"{account_number}.{photo_ext}")
            with open(photo_path, "wb") as f:
                f.write(photo_bytes)
            new_photo_path = photo_path

        cur.execute(
            """UPDATE accounts
               SET name = ?, email = ?, address = ?, mobile_number = ?,
                   upi_id = ?, profile_photo_path = ?
               WHERE account_number = ?""",
            (new_name, new_email, new_address, new_mobile, new_upi, new_photo_path, account_number),
        )
        conn.commit()
        conn.close()
        return True, "Profile updated successfully"

    def delete_account_streamlit(self, account_number, pin):
        conn = get_connection()
        cur = conn.cursor()
        row = self._get_account(cur, account_number, pin)
        if not row:
            conn.close()
            return False, "Invalid account number or PIN"

        cur.execute("DELETE FROM transactions WHERE account_number = ?", (account_number,))
        cur.execute("DELETE FROM accounts WHERE account_number = ?", (account_number,))
        conn.commit()
        conn.close()
        return True, "Account deleted successfully"

    
    def transaction_history_streamlit(self, account_number, pin):
        conn = get_connection()
        cur = conn.cursor()
        row = self._get_account(cur, account_number, pin)
        if not row:
            conn.close()
            return False, "Invalid account number or PIN"

        cur.execute(
            """SELECT type, amount, balance_after, description, date, time
               FROM transactions WHERE account_number = ?
               ORDER BY id DESC""",
            (account_number,),
        )
        rows = cur.fetchall()
        conn.close()

        result = []
        for r in rows:
            result.append({
                "type": r["type"],
                "amount": r["amount"],
                "balance_after": r["balance_after"],
                "description": r["description"],
                "date": r["date"],
                "date_time": r["time"],
            })
        return True, result

    
    def resolve_upi_identifier(self, identifier: str):
        """Given a UPI ID (9876543210@enzbank), a bare mobile number, or an
        account number, return the matching account_number, or None."""
        identifier = (identifier or "").strip()
        if not identifier:
            return None

        conn = get_connection()
        cur = conn.cursor()

        if "@" in identifier:
            mobile_part = identifier.split("@")[0]
            cur.execute("SELECT account_number FROM accounts WHERE upi_id = ?", (identifier,))
        elif identifier.isdigit() and len(identifier) == 10:
            cur.execute("SELECT account_number FROM accounts WHERE mobile_number = ?", (identifier,))
        else:
            cur.execute("SELECT account_number FROM accounts WHERE account_number = ?", (identifier,))

        row = cur.fetchone()
        conn.close()
        return row["account_number"] if row else None

    def upi_transfer_streamlit(self, sender_account, sender_pin, recipient_identifier, amount):
        """Instant transfer using the receiver's UPI ID or mobile number,
        moving money bank-balance to bank-balance (like real UPI)."""
        receiver_account = self.resolve_upi_identifier(recipient_identifier)
        if not receiver_account:
            return False, "No account found for that UPI ID / mobile number."
        return self.transfer_streamlit(sender_account, sender_pin, receiver_account, amount)

    
    def mobile_recharge_streamlit(self, account_number, pin, recharge_mobile, operator, amount, source="bank"):
        if amount <= 0:
            return False, "Amount must be greater than zero"
        if not (recharge_mobile.isdigit() and len(recharge_mobile) == 10):
            return False, "Enter a valid 10-digit mobile number to recharge."

        conn = get_connection()
        cur = conn.cursor()
        row = self._get_account(cur, account_number, pin)
        if not row:
            conn.close()
            return False, "Invalid account number or PIN"
        block_reason = _status_block_reason(row)
        if block_reason:
            conn.close()
            return False, block_reason

        balance_field = "wallet_balance" if source == "wallet" else "balance"
        if row[balance_field] < amount:
            conn.close()
            return False, f"Insufficient {'wallet' if source == 'wallet' else 'bank'} balance"

        new_value = row[balance_field] - amount
        cur.execute(
            f"UPDATE accounts SET {balance_field} = ? WHERE account_number = ?",
            (new_value, account_number),
        )
        self._log_transaction(
            cur, account_number, "Mobile Recharge", amount, new_value,
            f"Recharge for {recharge_mobile} ({operator}) via {source} balance"
        )
        conn.commit()
        conn.close()
        return True, f"₹{amount:.2f} recharge successful for {recharge_mobile} ({operator})"

    
    def admin_login_streamlit(self, username, password):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM admins WHERE username = ?", (username,))
        row = cur.fetchone()
        conn.close()
        if not row or row["password_hash"] != _hash_pin(password):
            return False, "Invalid admin username or password"
        return True, username

    def admin_streamlit(self):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM accounts ORDER BY created_at DESC")
        accounts = [dict(r) for r in cur.fetchall()]
        conn.close()

        total_balance = sum(a["balance"] for a in accounts)
        total_wallet = sum(a["wallet_balance"] for a in accounts)
        return {
            "total_accounts": len(accounts),
            "total_balance": round(total_balance, 2),
            "total_wallet_balance": round(total_wallet, 2),
            "accounts": accounts,
        }

    def _log_admin_action(self, cur, admin_username, account_number, action):
        date_str, time_str = _now()
        cur.execute(
            """INSERT INTO admin_actions (admin_username, account_number, action, date, time)
               VALUES (?, ?, ?, ?, ?)""",
            (admin_username, account_number, action, date_str, time_str),
        )

    def _admin_set_status(self, admin_username, account_number, new_status, action_label):
        """
        Internal helper: the ONLY thing admin actions are allowed to touch
        is the `status` column. Name, email, address, mobile, balances, PIN,
        and photo are never written to by any admin-facing method.
        """
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM accounts WHERE account_number = ?", (account_number,))
        if not cur.fetchone():
            conn.close()
            return False, "Account not found"

        cur.execute(
            "UPDATE accounts SET status = ? WHERE account_number = ?",
            (new_status, account_number),
        )
        self._log_admin_action(cur, admin_username, account_number, action_label)
        conn.commit()
        conn.close()
        return True, f"Account {account_number}: {action_label}"

    def admin_freeze_account(self, admin_username, account_number):
        return self._admin_set_status(admin_username, account_number, STATUS_FROZEN, "Frozen")

    def admin_unfreeze_account(self, admin_username, account_number):
        return self._admin_set_status(admin_username, account_number, STATUS_ACTIVE, "Unfrozen")

    def admin_suspend_account(self, admin_username, account_number):
        return self._admin_set_status(admin_username, account_number, STATUS_SUSPENDED, "Suspended")

    def admin_resume_account(self, admin_username, account_number):
        return self._admin_set_status(admin_username, account_number, STATUS_ACTIVE, "Resumed")

    def admin_delete_account(self, admin_username, account_number):
        """Admin can delete an account (e.g. fraud, closure request) but
        this is logged in admin_actions before the row is removed."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM accounts WHERE account_number = ?", (account_number,))
        if not cur.fetchone():
            conn.close()
            return False, "Account not found"

        self._log_admin_action(cur, admin_username, account_number, "Deleted")
        conn.commit()

        cur.execute("DELETE FROM transactions WHERE account_number = ?", (account_number,))
        cur.execute("DELETE FROM accounts WHERE account_number = ?", (account_number,))
        conn.commit()
        conn.close()
        return True, f"Account {account_number} deleted by admin"

    def admin_action_log_streamlit(self, limit=50):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM admin_actions ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
